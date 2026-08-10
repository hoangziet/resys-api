from __future__ import annotations

import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

from app import create_app
from core import database
from core.config import settings


def _client(tmp_path: Path, monkeypatch) -> TestClient:
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "db.sqlite3")
    return TestClient(create_app())


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
