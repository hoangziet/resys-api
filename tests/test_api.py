from __future__ import annotations

import math
import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app import create_app
from core import database
from core.config import settings


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    from core.rate_limit import limiter

    limiter.reset()

@pytest.fixture(autouse=True)
def _disable_rate_limit():
    with patch("slowapi.extension.Limiter.limit", return_value=lambda f: f):
        yield

def _client(tmp_path: Path, monkeypatch) -> TestClient:
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "db.sqlite3")
    return TestClient(create_app())


def _admin_headers(client: TestClient) -> dict:
    token = _login(client, settings.admin_username, settings.admin_password)
    return {"Authorization": f"Bearer {token}"}


def _login(client: TestClient, username: str = "learner", password: str = "Learner123") -> str:
    response = client.post(
        "/api/v1/auth/token",
        data={"username": username, "password": password},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def test_init_db_repairs_legacy_sqlite_schema(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "legacy.sqlite3"
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'learner'
        );
        CREATE TABLE user_history (
            user_id INTEGER NOT NULL,
            item_idx INTEGER NOT NULL,
            PRIMARY KEY (user_id, item_idx)
        );
        CREATE TABLE recommendation_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            username TEXT,
            strategy TEXT NOT NULL,
            latency_ms REAL NOT NULL,
            history TEXT,
            results TEXT
        );
        INSERT INTO users (username, password_hash, role)
        VALUES ('admin', 'not-a-bcrypt-hash', 'admin');
        """
    )
    conn.commit()
    conn.close()

    monkeypatch.setattr(database, "DB_PATH", db_path)
    database.init_db()

    conn = sqlite3.connect(db_path)
    columns = {row[1] for row in conn.execute("PRAGMA table_info(user_history)")}
    assert {"order_idx", "added_at"}.issubset(columns)
    assert conn.execute("SELECT version_num FROM alembic_version").fetchone()[0]

    admin = database.get_user_by_username(settings.admin_username)
    assert admin is not None
    assert database.verify_password(settings.admin_password, admin["password_hash"])


def test_auth_history_and_recommendation_flow(tmp_path: Path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)
    token = _login(client)
    headers = {"Authorization": f"Bearer {token}"}

    response = client.post("/api/v1/history/?item_idx=1", headers=headers)
    assert response.status_code == 200, response.text

    response = client.get("/api/v1/history/", headers=headers)
    assert response.status_code == 200, response.text
    assert [item["item_idx"] for item in response.json()["history"]] == [1]

    response = client.post(
        "/api/v1/recommendations/for-you",
        headers=headers,
        json={"limit": 3},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["source"] in {"bert4rec_personalized", "popular_fallback_error"}
    assert len(payload["items"]) <= 3


def test_invalid_similar_course_returns_404(tmp_path: Path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)
    token = _login(client)

    response = client.post(
        "/api/v1/recommendations/similar/999999",
        headers={"Authorization": f"Bearer {token}"},
        json={"limit": 3},
    )
    assert response.status_code == 404


def test_course_catalog_tables_are_seeded(tmp_path: Path, monkeypatch) -> None:
    _client(tmp_path, monkeypatch)

    conn = sqlite3.connect(tmp_path / "db.sqlite3")
    fr_count = conn.execute("SELECT COUNT(*) FROM courses").fetchone()[0]
    en_count = conn.execute("SELECT COUNT(*) FROM courses_en").fetchone()[0]
    assert fr_count > 0
    assert fr_count == en_count

    orphans = conn.execute(
        "SELECT COUNT(*) FROM courses_en e "
        "LEFT JOIN courses f ON f.item_idx = e.item_idx "
        "WHERE f.item_idx IS NULL"
    ).fetchone()[0]
    assert orphans == 0

    # Seeding is idempotent: a second init_db must not duplicate or drop rows.
    database.init_db()
    assert conn.execute("SELECT COUNT(*) FROM courses").fetchone()[0] == fr_count
    assert conn.execute("SELECT COUNT(*) FROM courses_en").fetchone()[0] == en_count
    conn.close()


def test_course_detail_supports_both_languages(tmp_path: Path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)
    headers = {"Authorization": f"Bearer {_login(client)}"}

    en_response = client.get("/api/v1/courses/1?lang=en", headers=headers)
    assert en_response.status_code == 200, en_response.text
    fr_response = client.get("/api/v1/courses/1?lang=fr", headers=headers)
    assert fr_response.status_code == 200, fr_response.text

    en_course = en_response.json()
    fr_course = fr_response.json()

    assert en_course["item_idx"] == fr_course["item_idx"] == 1
    assert en_course["language"] == "en"
    assert fr_course["language"] == "fr"
    assert en_course["title"] != fr_course["title"]

    # thumbnail_path lives on courses_en but a thumbnail is language-neutral
    assert en_course["thumbnail_url"].startswith("http")
    assert fr_course["thumbnail_url"] == en_course["thumbnail_url"]


def test_language_does_not_affect_model_ranking(tmp_path: Path, monkeypatch) -> None:
    """English is display-only: it must not reach model input or ranking."""
    client = _client(tmp_path, monkeypatch)
    headers = {"Authorization": f"Bearer {_login(client)}"}

    def ranked_idxs(lang: str) -> list[int]:
        response = client.post(
            f"/api/v1/recommendations/similar/1?lang={lang}",
            headers=headers,
            json={"limit": 10},
        )
        assert response.status_code == 200, response.text
        return [item["item_idx"] for item in response.json()["items"]]

    assert ranked_idxs("en") == ranked_idxs("fr")


def _courses(client: TestClient, headers: dict, query: str = "") -> dict:
    response = client.get(f"/api/v1/courses/?{query}", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def test_course_filters_endpoint_lists_options(tmp_path: Path, monkeypatch) -> None:
    """Also guards route ordering: /courses/filters must not parse as /{course_id}."""
    client = _client(tmp_path, monkeypatch)
    headers = {"Authorization": f"Bearer {_login(client)}"}

    response = client.get("/api/v1/courses/filters?lang=en", headers=headers)
    assert response.status_code == 200, response.text
    filters = response.json()["filters"]

    assert set(filters) == {"difficulty", "theme", "software", "job_type", "type"}
    for group in ("difficulty", "theme", "software", "type"):
        assert filters[group], f"expected values for {group}"
        for option in filters[group]:
            assert option["count"] > 0
            assert option["value"] and option["label"]

    # difficulty slugs are derived from the level digit, so they are the same in
    # both languages and ordered by level
    assert [o["value"] for o in filters["difficulty"]] == [
        "beginner",
        "intermediate",
        "advanced",
    ]


def test_course_pagination_is_applied_in_the_database(tmp_path: Path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)
    headers = {"Authorization": f"Bearer {_login(client)}"}

    page1 = _courses(client, headers, "page=1&limit=12")
    page2 = _courses(client, headers, "page=2&limit=12")

    assert len(page1["courses"]) == 12
    assert len(page2["courses"]) == 12

    total = page1["pagination"]["total"]
    assert total > 12
    assert page1["pagination"] == {
        "page": 1,
        "limit": 12,
        "total": total,
        "total_pages": math.ceil(total / 12),
    }
    # total is independent of the page being viewed
    assert page2["pagination"]["total"] == total

    idxs1 = [c["item_idx"] for c in page1["courses"]]
    idxs2 = [c["item_idx"] for c in page2["courses"]]
    assert set(idxs1).isdisjoint(idxs2)

    # a page past the end is empty but still reports the real total
    last = _courses(client, headers, f"page={page1['pagination']['total_pages'] + 5}&limit=12")
    assert last["courses"] == []
    assert last["pagination"]["total"] == total


def test_course_pagination_rejects_out_of_range_params(tmp_path: Path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)
    headers = {"Authorization": f"Bearer {_login(client)}"}

    for query in ("page=0", "limit=0", "limit=101"):
        response = client.get(f"/api/v1/courses/?{query}", headers=headers)
        assert response.status_code == 422, f"{query} -> {response.status_code}"


def test_course_filters_combine(tmp_path: Path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)
    headers = {"Authorization": f"Bearer {_login(client)}"}

    unfiltered = _courses(client, headers, "limit=1")["pagination"]["total"]
    beginner = _courses(client, headers, "difficulty=beginner&limit=1")["pagination"]["total"]
    excel = _courses(client, headers, "software=excel&limit=1")["pagination"]["total"]
    both = _courses(
        client, headers, "difficulty=beginner&software=excel&limit=1"
    )["pagination"]["total"]

    # a filter narrows, and different filters AND together
    assert 0 < beginner < unfiltered
    assert 0 < excel < unfiltered
    assert both <= min(beginner, excel)

    # values within one filter OR together
    excel_or_teams = _courses(
        client, headers, "software=excel&software=teams&limit=1"
    )["pagination"]["total"]
    teams = _courses(client, headers, "software=teams&limit=1")["pagination"]["total"]
    assert excel_or_teams >= max(excel, teams)
    assert excel_or_teams <= excel + teams


def test_software_filter_matches_whole_tokens_only(tmp_path: Path, monkeypatch) -> None:
    """`software=teams` must not match the distinct token "Skype VS Teams".

    theme/software/job are comma-separated multilabel columns, so a substring
    LIKE would conflate separate values.
    """
    client = _client(tmp_path, monkeypatch)
    headers = {"Authorization": f"Bearer {_login(client)}"}

    conn = sqlite3.connect(tmp_path / "db.sqlite3")
    skype_vs_teams = [
        row[0]
        for row in conn.execute(
            "SELECT item_idx FROM courses_en WHERE software = 'Skype VS Teams'"
        )
    ]
    conn.close()
    if not skype_vs_teams:
        pytest.skip("no course with software exactly 'Skype VS Teams'")

    total = _courses(client, headers, "software=teams&limit=1")["pagination"]["total"]
    matched: list[int] = []
    for page in range(1, math.ceil(total / 100) + 1):
        matched += [
            c["item_idx"]
            for c in _courses(client, headers, f"software=teams&page={page}&limit=100")["courses"]
        ]

    assert set(matched).isdisjoint(skype_vs_teams)


def test_course_search_and_filter_together(tmp_path: Path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)
    headers = {"Authorization": f"Bearer {_login(client)}"}

    searched = _courses(client, headers, "q=Excel&limit=50")
    assert searched["pagination"]["total"] > 0
    for course in searched["courses"]:
        haystack = f"{course['title']} {course['description']}".lower()
        assert "excel" in haystack

    # LIKE wildcards in user input are escaped, not interpreted: "%" must not
    # behave as match-everything. (A literal "%" may legitimately appear in some
    # descriptions, so compare against the unfiltered total rather than zero.)
    everything = _courses(client, headers, "limit=1")["pagination"]["total"]
    wild = _courses(client, headers, "q=%25&limit=1")
    assert wild["pagination"]["total"] < everything


def test_search_matches_tokens_across_all_searchable_columns(
    tmp_path: Path, monkeypatch
) -> None:
    client = _client(tmp_path, monkeypatch)
    headers = {"Authorization": f"Bearer {_login(client)}"}

    # A term that lives in `software`, not in title/description, still matches.
    by_software = _courses(client, headers, "q=OneDrive&limit=50")
    assert by_software["pagination"]["total"] > 0

    # Multiple tokens AND together, so adding a token can only narrow.
    one = _courses(client, headers, "q=Teams&limit=1")["pagination"]["total"]
    two = _courses(client, headers, "q=Teams+meeting&limit=1")["pagination"]["total"]
    assert one > 0
    assert two <= one


# --------------------------------------------------------------------------
# Monitoring
# --------------------------------------------------------------------------


def test_latency_percentiles_are_exact() -> None:
    values = [float(n) for n in range(1, 101)]  # 1..100
    summary = database._summarize_latencies(values)

    assert summary["count"] == 100
    assert summary["avg"] == 50.5
    assert summary["min"] == 1.0
    assert summary["max"] == 100.0
    # Nearest-rank: ceil(0.50*100)=50 -> the 50th value.
    assert summary["p50"] == 50.0
    assert summary["p95"] == 95.0
    assert summary["p99"] == 99.0
    # Median and P50 are the same percentile, not two different statistics.
    assert summary["median"] == summary["p50"]

    empty = database._summarize_latencies([])
    assert empty["count"] == 0
    assert empty["p99"] == 0.0


def test_recommendation_requests_are_logged_with_endpoint_and_status(
    tmp_path: Path, monkeypatch
) -> None:
    client = _client(tmp_path, monkeypatch)
    headers = {"Authorization": f"Bearer {_login(client)}"}

    response = client.post(
        "/api/v1/recommendations/popular", headers=headers, json={"limit": 3}
    )
    assert response.status_code == 200, response.text

    logs = client.get(
        "/api/v1/admin/recommendation-logs", headers=_admin_headers(client)
    ).json()["logs"]
    assert logs, "middleware should have written a log row"
    latest = logs[0]
    assert latest["endpoint"] == "/api/v1/recommendations/popular"
    assert latest["status_code"] == 200
    assert latest["latency_ms"] > 0

    stats = client.get(
        "/api/v1/admin/latency-stats?hours=24", headers=_admin_headers(client)
    ).json()
    assert stats["overall"]["count"] >= 1
    assert stats["overall"]["median"] == stats["overall"]["p50"]
    assert any(e["endpoint"] == "/api/v1/recommendations/popular" for e in stats["by_endpoint"])


def test_failed_recommendation_request_is_still_measured(
    tmp_path: Path, monkeypatch
) -> None:
    """A handler that raises must still produce a row, with the real status."""
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "db.sqlite3")
    client = TestClient(create_app(), raise_server_exceptions=False)
    headers = {"Authorization": f"Bearer {_login(client)}"}

    from models.catalog import catalog

    def boom(*args, **kwargs):
        raise RuntimeError("induced failure")

    monkeypatch.setattr(catalog, "get_popular_items", boom)

    response = client.post(
        "/api/v1/recommendations/popular", headers=headers, json={"limit": 3}
    )
    assert response.status_code == 500

    monkeypatch.undo()
    logs = client.get(
        "/api/v1/admin/recommendation-logs", headers=_admin_headers(client)
    ).json()["logs"]
    assert any(row["status_code"] == 500 for row in logs), (
        "a failing request must be measured; percentiles built only from "
        "successes hide the incidents monitoring exists to catch"
    )


# --------------------------------------------------------------------------
# New course -> recommendation pipeline
# --------------------------------------------------------------------------


def _create_course(client: TestClient, **overrides) -> dict:
    payload = {
        "title": "Intro to Power BI Dashboards",
        "description": "Build a first report.",
        "difficulty": "beginner",
        "software": "Power BI",
        "theme": "Analyze",
        "job_type": "Project Manager",
        "type": "tutorial",
    }
    payload.update(overrides)
    response = client.post(
        "/api/v1/admin/courses", headers=_admin_headers(client), json=payload
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_new_course_is_never_fed_to_bert4rec(tmp_path: Path, monkeypatch) -> None:
    """The mask-token collision guard.

    mask_token == n_items + 1, so the first item_idx past the training catalog is
    numerically identical to [MASK]. A new course may enter user_history (it is
    application data) but must never reach predict().
    """
    client = _client(tmp_path, monkeypatch)
    headers = {"Authorization": f"Bearer {_login(client)}"}

    from api.recommendations import get_model, model_history

    model = get_model()
    assert model is not None

    created = _create_course(client)
    item_idx = created["item_idx"]
    assert item_idx > model.n_items, "a new course must sit outside the model vocabulary"

    # The exact hazard: the mask token is never passed through as an item.
    assert model_history([model.mask_token]) == []
    assert model_history([item_idx]) == []
    assert model_history([1, item_idx, 2]) == [1, 2]

    # History accepts it (application data), and for-you still succeeds.
    assert client.post(f"/api/v1/history/?item_idx={item_idx}", headers=headers).status_code == 200
    response = client.post("/api/v1/recommendations/for-you", headers=headers, json={"limit": 5})
    assert response.status_code == 200, response.text
    assert all(item["item_idx"] <= model.n_items for item in response.json()["items"])


def test_new_course_is_searchable_but_not_similarity_ready(
    tmp_path: Path, monkeypatch
) -> None:
    client = _client(tmp_path, monkeypatch)
    headers = {"Authorization": f"Bearer {_login(client)}"}

    created = _create_course(client)
    item_idx = created["item_idx"]
    availability = created["recommendation_availability"]
    assert availability["search_and_filter"] is True
    assert availability["trending"] is True
    assert availability["text_similarity"] is False
    assert availability["bert4rec"] is False
    assert availability["embedding_status"] == "pending"

    # Immediately searchable and filterable.
    found = _courses(client, headers, "q=Power+BI+Dashboards&limit=20")
    assert item_idx in [c["item_idx"] for c in found["courses"]]

    filters = client.get("/api/v1/courses/filters?lang=en", headers=headers).json()["filters"]
    assert "power_bi" in [o["value"] for o in filters["software"]]

    # Similarity refuses with 409 (exists but unembedded), not 404 (missing).
    response = client.post(
        f"/api/v1/recommendations/similar/{item_idx}", headers=headers, json={"limit": 5}
    )
    assert response.status_code == 409, response.text
    assert "embedding" in response.json()["detail"].lower()

    missing = client.post(
        "/api/v1/recommendations/similar/999999", headers=headers, json={"limit": 5}
    )
    assert missing.status_code == 404


def test_pipeline_status_reports_required_actions(tmp_path: Path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)
    admin = _admin_headers(client)

    before = client.get("/api/v1/admin/pipeline-status", headers=admin).json()
    assert before["text_similarity"]["action_required"] is False

    created = _create_course(client)
    after = client.get("/api/v1/admin/pipeline-status", headers=admin).json()

    assert after["catalog"]["courses"] == before["catalog"]["courses"] + 1
    assert after["text_similarity"]["action_required"] is True
    assert created["item_idx"] in after["text_similarity"]["pending_item_idxs"]
    assert after["bert4rec"]["action_required"] is True
    assert after["trending"]["action_required"] is False


def test_trending_ranks_by_interaction_count(tmp_path: Path, monkeypatch) -> None:
    # Built for the side effects: patches DB_PATH and seeds the catalog this reads.
    _client(tmp_path, monkeypatch)

    conn = sqlite3.connect(tmp_path / "db.sqlite3")
    conn.executemany(
        "INSERT OR IGNORE INTO users (id, username, password_hash, role) "
        "VALUES (?, ?, 'x', 'learner')",
        [(901, "u1"), (902, "u2")],
    )
    # item 7 interacted with twice, item 9 once.
    conn.executemany(
        "INSERT OR REPLACE INTO user_history (user_id, item_idx, order_idx, added_at) "
        "VALUES (?, ?, 0, CURRENT_TIMESTAMP)",
        [(901, 7), (902, 7), (901, 9)],
    )
    conn.commit()
    conn.close()

    trending = database.get_trending_items(limit=5, days=30)
    assert trending[:2] == [7, 9], f"expected interaction-count order, got {trending}"


# --------------------------------------------------------------------------
# Admin course CRUD
# --------------------------------------------------------------------------


def test_admin_course_update_and_delete(tmp_path: Path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)
    admin = _admin_headers(client)
    headers = {"Authorization": f"Bearer {_login(client)}"}

    item_idx = _create_course(client)["item_idx"]

    updated = client.put(
        f"/api/v1/admin/courses/{item_idx}",
        headers=admin,
        json={"title": "Renamed Course", "difficulty": "advanced"},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["course"]["title"] == "Renamed Course"

    detail = client.get(f"/api/v1/courses/{item_idx}", headers=headers).json()
    assert detail["title"] == "Renamed Course"
    assert detail["difficulty"].startswith("3")

    deleted = client.delete(f"/api/v1/admin/courses/{item_idx}", headers=admin)
    assert deleted.status_code == 200, deleted.text

    # CASCADE cleared the translation and facet rows.
    conn = sqlite3.connect(tmp_path / "db.sqlite3")

    def row_count(table: str) -> int:
        sql = f"SELECT COUNT(*) FROM {table} WHERE item_idx = ?"
        return conn.execute(sql, (item_idx,)).fetchone()[0]

    assert row_count("courses") == 0
    assert row_count("courses_en") == 0
    assert row_count("course_facets") == 0
    conn.close()

    assert client.get(f"/api/v1/courses/{item_idx}", headers=headers).status_code == 404


def test_admin_delete_refuses_model_vocabulary_course(tmp_path: Path, monkeypatch) -> None:
    """Deleting a course the checkpoint still predicts needs an explicit override."""
    client = _client(tmp_path, monkeypatch)
    admin = _admin_headers(client)

    blocked = client.delete("/api/v1/admin/courses/1", headers=admin)
    assert blocked.status_code == 409, blocked.text
    assert "force" in blocked.json()["detail"].lower()

    forced = client.delete("/api/v1/admin/courses/1?force=true", headers=admin)
    assert forced.status_code == 200, forced.text


def test_admin_course_validation_and_authorization(tmp_path: Path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)

    # Learners cannot manage courses.
    learner = {"Authorization": f"Bearer {_login(client)}"}
    assert client.post(
        "/api/v1/admin/courses", headers=learner, json={"title": "Nope"}
    ).status_code == 403

    admin = _admin_headers(client)
    assert client.post(
        "/api/v1/admin/courses", headers=admin, json={"title": ""}
    ).status_code == 422
    assert client.post(
        "/api/v1/admin/courses",
        headers=admin,
        json={"title": "X", "difficulty": "expert"},
    ).status_code == 422


