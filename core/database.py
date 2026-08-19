from __future__ import annotations

import contextlib
import logging
import math
import sqlite3
from collections.abc import Generator

import bcrypt

from core.catalog_seed import fetch_courses, rebuild_facets_for_item, seed_courses
from core.config import settings

log = logging.getLogger(__name__)

DB_PATH = settings.sqlite_path

Conn = sqlite3.Connection


def get_connection() -> Conn:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextlib.contextmanager
def connection() -> Generator[Conn, None, None]:
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"), hashed_password.encode("utf-8")
        )
    except ValueError:
        log.warning("Stored password hash is not a valid bcrypt hash")
        return False


def _has_valid_bcrypt_hash(hashed_password: str) -> bool:
    try:
        bcrypt.checkpw(b"health-check", hashed_password.encode("utf-8"))
        return True
    except ValueError:
        return False


def _get_user_id(cursor: sqlite3.Cursor, username: str) -> int | None:
    cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
    row = cursor.fetchone()
    return row["id"] if row else None


def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'learner'
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_history (
        user_id INTEGER NOT NULL,
        item_idx INTEGER NOT NULL,
        order_idx INTEGER NOT NULL DEFAULT 0,
        added_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (user_id, item_idx),
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS courses (
        item_idx INTEGER PRIMARY KEY,
        item_id TEXT,
        title TEXT NOT NULL,
        description TEXT,
        text TEXT,
        language TEXT DEFAULT 'fr',
        difficulty TEXT,
        theme TEXT,
        software TEXT,
        job TEXT,
        type TEXT,
        duration REAL,
        embedding_status TEXT DEFAULT 'ready'
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS courses_en (
        item_idx INTEGER PRIMARY KEY,
        item_id TEXT,
        title TEXT NOT NULL,
        description TEXT,
        text TEXT,
        language TEXT DEFAULT 'en',
        difficulty TEXT,
        theme TEXT,
        software TEXT,
        job TEXT,
        type TEXT,
        duration REAL,
        thumbnail_path TEXT,
        FOREIGN KEY (item_idx) REFERENCES courses(item_idx) ON DELETE CASCADE
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS course_facets (
        item_idx INTEGER NOT NULL,
        kind TEXT NOT NULL,
        lang TEXT NOT NULL,
        slug TEXT NOT NULL,
        label TEXT NOT NULL,
        PRIMARY KEY (item_idx, kind, lang, slug),
        FOREIGN KEY (item_idx) REFERENCES courses(item_idx) ON DELETE CASCADE
    );
    """)
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS ix_course_facets_lookup "
        "ON course_facets (kind, lang, slug)"
    )

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS recommendation_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        username TEXT,
        strategy TEXT NOT NULL,
        latency_ms REAL NOT NULL,
        history TEXT,
        results TEXT
    );
    """)
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS ix_rec_logs_timestamp ON recommendation_logs (timestamp)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS ix_rec_logs_username ON recommendation_logs (username)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS ix_rec_logs_strategy ON recommendation_logs (strategy)"
    )

    conn.commit()

    _ensure_sqlite_columns(cursor)
    conn.commit()

    seed_courses(cursor)
    conn.commit()

    _ensure_seed_user(
        cursor,
        username=settings.learner_username,
        password=settings.learner_password,
        role="learner",
    )
    _ensure_seed_user(
        cursor,
        username=settings.admin_username,
        password=settings.admin_password,
        role="admin",
    )
    conn.commit()

    cursor.execute(
        "DELETE FROM recommendation_logs WHERE timestamp < datetime('now', ?)",
        (f"-{settings.log_retention_days} days",),
    )
    if cursor.rowcount > 0:
        conn.commit()
        log.info(
            "Cleaned up %d recommendation logs older than %d days",
            cursor.rowcount,
            settings.log_retention_days,
        )

    conn.close()


def _ensure_sqlite_columns(cursor: sqlite3.Cursor) -> None:
    """Apply small forward-compatible SQLite fixes for existing local volumes."""
    table_columns = {
        row["name"] for row in cursor.execute("PRAGMA table_info(user_history)")
    }
    if "order_idx" not in table_columns:
        cursor.execute(
            "ALTER TABLE user_history ADD COLUMN order_idx INTEGER NOT NULL DEFAULT 0"
        )
    if "added_at" not in table_columns:
        cursor.execute(
            "ALTER TABLE user_history ADD COLUMN added_at DATETIME DEFAULT CURRENT_TIMESTAMP"
        )

    log_columns = {
        row["name"] for row in cursor.execute("PRAGMA table_info(recommendation_logs)")
    }
    if "endpoint" not in log_columns:
        cursor.execute("ALTER TABLE recommendation_logs ADD COLUMN endpoint TEXT")
    if "status_code" not in log_columns:
        cursor.execute("ALTER TABLE recommendation_logs ADD COLUMN status_code INTEGER")
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS ix_rec_logs_endpoint ON recommendation_logs (endpoint)"
    )

    course_columns = {
        row["name"] for row in cursor.execute("PRAGMA table_info(courses)")
    }
    if course_columns and "embedding_status" not in course_columns:
        # Existing rows all came from the CSV, so they already have embeddings.
        cursor.execute(
            "ALTER TABLE courses ADD COLUMN embedding_status TEXT DEFAULT 'ready'"
        )
        cursor.execute("UPDATE courses SET embedding_status = 'ready'")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS alembic_version (
        version_num VARCHAR(32) NOT NULL,
        CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
    );
    """)
    cursor.execute("SELECT COUNT(*) AS count FROM alembic_version")
    if cursor.fetchone()["count"] == 0:
        cursor.execute(
            "INSERT INTO alembic_version (version_num) VALUES (?)",
            ("c31f53b0d12f",),
        )


def _ensure_seed_user(
    cursor: sqlite3.Cursor, username: str, password: str, role: str
) -> None:
    cursor.execute(
        "SELECT id, password_hash FROM users WHERE username = ?",
        (username,),
    )
    row = cursor.fetchone()
    if row is None:
        cursor.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
            (username, hash_password(password), role),
        )
        log.info("Seeded %s user: %s", role, username)
        return

    if not _has_valid_bcrypt_hash(row["password_hash"]):
        cursor.execute(
            "UPDATE users SET password_hash = ?, role = ? WHERE id = ?",
            (hash_password(password), role, row["id"]),
        )
        log.warning("Repaired invalid password hash for configured %s user", role)


def get_user_by_username(username: str) -> dict | None:
    with connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        row = cursor.fetchone()
        return dict(row) if row else None


def create_user(username: str, password_hash: str, role: str = "learner") -> bool:
    with connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
                (username, password_hash, role),
            )
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False


def get_courses(lang: str = "en") -> list[dict]:
    """Read the full localized catalog for the in-memory display cache.

    ``lang="en"`` reads ``courses_en`` (English text plus ``thumbnail_path``),
    anything else reads the French ``courses`` table.
    """
    table = "courses_en" if lang == "en" else "courses"
    with connection() as conn:
        cursor = conn.cursor()
        try:
            return [dict(row) for row in fetch_courses(cursor, table)]
        except sqlite3.Error:
            log.exception("Failed to read catalog table %s", table)
            return []


def course_exists(item_idx: int) -> bool:
    """Whether the course is in the catalog at all (regardless of recommender state)."""
    with connection() as conn:
        row = conn.execute(
            "SELECT 1 FROM courses WHERE item_idx = ?", (item_idx,)
        ).fetchone()
        return row is not None


def get_course_admin_row(item_idx: int) -> dict | None:
    """Full course row for admin views, including embedding_status."""
    with connection() as conn:
        row = conn.execute(
            'SELECT "item_idx", "item_id", "title", "description", "language", '
            '"difficulty", "theme", "software", "job", "type", "duration", '
            '"embedding_status" FROM courses WHERE item_idx = ?',
            (item_idx,),
        ).fetchone()
        return dict(row) if row else None


def get_embedding_statuses(item_idxs: list[int]) -> dict[int, str]:
    """embedding_status for a batch of courses, for annotating admin listings."""
    if not item_idxs:
        return {}
    placeholders = ", ".join("?" for _ in item_idxs)
    with connection() as conn:
        rows = conn.execute(
            f"SELECT item_idx, embedding_status FROM courses WHERE item_idx IN ({placeholders})",
            item_idxs,
        ).fetchall()
        return {int(r["item_idx"]): (r["embedding_status"] or "ready") for r in rows}


def create_course(fields: dict) -> int | None:
    """Insert a course into both catalogs and rebuild its facets.

    Returns the allocated ``item_idx``. The new row is written to ``courses`` (the
    FK parent) and ``courses_en`` with the same text, and marked
    ``embedding_status='pending'``: it is searchable at once but stays out of
    text-similarity results until the offline embedding job runs.
    """
    with connection() as conn:
        cursor = conn.cursor()
        try:
            row = cursor.execute("SELECT COALESCE(MAX(item_idx), 0) + 1 FROM courses").fetchone()
            item_idx = int(row[0])

            shared = (
                item_idx,
                fields.get("item_id") or str(item_idx),
                fields["title"],
                fields.get("description"),
                fields.get("text") or fields["title"],
                fields.get("difficulty"),
                fields.get("theme"),
                fields.get("software"),
                fields.get("job"),
                fields.get("type"),
                fields.get("duration"),
            )
            cursor.execute(
                'INSERT INTO courses ("item_idx", "item_id", "title", "description", '
                '"text", "language", "difficulty", "theme", "software", "job", "type", '
                '"duration", "embedding_status") '
                "VALUES (?, ?, ?, ?, ?, 'fr', ?, ?, ?, ?, ?, ?, 'pending')",
                shared,
            )
            cursor.execute(
                'INSERT INTO courses_en ("item_idx", "item_id", "title", "description", '
                '"text", "language", "difficulty", "theme", "software", "job", "type", '
                '"duration", "thumbnail_path") '
                "VALUES (?, ?, ?, ?, ?, 'en', ?, ?, ?, ?, ?, ?, ?)",
                (*shared, fields.get("thumbnail_path")),
            )
            rebuild_facets_for_item(cursor, item_idx)
            conn.commit()
            log.info("Created course item_idx=%d title=%r", item_idx, fields["title"])
            return item_idx
        except sqlite3.Error:
            log.exception("Failed to create course %r", fields.get("title"))
            conn.rollback()
            return None


_UPDATABLE_COLUMNS = (
    "title",
    "description",
    "difficulty",
    "theme",
    "software",
    "job",
    "type",
    "duration",
    "thumbnail_path",
)


def update_course(item_idx: int, fields: dict) -> bool:
    """Apply a partial update to both catalogs and rebuild the course's facets."""
    updates = {k: v for k, v in fields.items() if k in _UPDATABLE_COLUMNS}
    if not updates:
        return False

    with connection() as conn:
        cursor = conn.cursor()
        try:
            if cursor.execute(
                "SELECT 1 FROM courses WHERE item_idx = ?", (item_idx,)
            ).fetchone() is None:
                return False

            # thumbnail_path only exists on courses_en.
            for table in ("courses", "courses_en"):
                columns = [
                    c
                    for c in updates
                    if c != "thumbnail_path" or table == "courses_en"
                ]
                if not columns:
                    continue
                assignments = ", ".join(f'"{c}" = ?' for c in columns)
                cursor.execute(
                    f"UPDATE {table} SET {assignments} WHERE item_idx = ?",
                    [*(updates[c] for c in columns), item_idx],
                )

            rebuild_facets_for_item(cursor, item_idx)
            conn.commit()
            log.info("Updated course item_idx=%d fields=%s", item_idx, sorted(updates))
            return True
        except sqlite3.Error:
            log.exception("Failed to update course item_idx=%d", item_idx)
            conn.rollback()
            return False


def delete_course(item_idx: int) -> bool:
    """Delete a course; CASCADE removes its courses_en and course_facets rows."""
    with connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM courses WHERE item_idx = ?", (item_idx,))
            deleted = cursor.rowcount > 0
            conn.commit()
            if deleted:
                log.info("Deleted course item_idx=%d", item_idx)
            return deleted
        except sqlite3.Error:
            log.exception("Failed to delete course item_idx=%d", item_idx)
            conn.rollback()
            return False


def count_courses() -> int:
    with connection() as conn:
        return int(conn.execute("SELECT COUNT(*) FROM courses").fetchone()[0])


def get_courses_pending_embedding(limit: int = 500) -> list[dict]:
    """Courses with no row in the text-embedding tensor yet."""
    with connection() as conn:
        rows = conn.execute(
            'SELECT "item_idx", "title", "text" FROM courses '
            "WHERE COALESCE(embedding_status, 'ready') <> 'ready' "
            "ORDER BY item_idx LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]


def mark_embeddings_ready(item_idxs: list[int]) -> int:
    if not item_idxs:
        return 0
    placeholders = ", ".join("?" for _ in item_idxs)
    with connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            f"UPDATE courses SET embedding_status = 'ready' WHERE item_idx IN ({placeholders})",
            item_idxs,
        )
        conn.commit()
        return cursor.rowcount


def get_trending_items(limit: int = 10, days: int = 30) -> list[int]:
    """Trending courses by real interaction counts from user_history.

    Replaces the previous stub (the lowest N item_idx). Any catalog course can
    trend, including admin-created ones, because this counts interactions rather
    than reading a precomputed artifact. Returns [] when there is no history, so
    callers can fall back to catalog order.
    """
    with connection() as conn:
        try:
            rows = conn.execute(
                "SELECT h.item_idx, COUNT(*) AS interactions "
                "FROM user_history h JOIN courses c ON c.item_idx = h.item_idx "
                "WHERE h.added_at >= datetime('now', ?) "
                "GROUP BY h.item_idx "
                "ORDER BY interactions DESC, h.item_idx ASC LIMIT ?",
                (f"-{int(days)} days", limit),
            ).fetchall()
            return [int(row["item_idx"]) for row in rows]
        except sqlite3.Error:
            log.exception("Failed to compute trending items")
            return []


def get_user_history(username: str) -> list[int]:
    with connection() as conn:
        cursor = conn.cursor()
        user_id = _get_user_id(cursor, username)
        if user_id is None:
            return []
        cursor.execute(
            "SELECT item_idx FROM user_history WHERE user_id = ? ORDER BY order_idx ASC",
            (user_id,),
        )
        return [row["item_idx"] for row in cursor.fetchall()]


def add_history_item(username: str, item_idx: int) -> bool:
    with connection() as conn:
        cursor = conn.cursor()
        user_id = _get_user_id(cursor, username)
        if user_id is None:
            return False
        try:
            cursor.execute(
                "SELECT COALESCE(MAX(order_idx), -1) + 1 FROM user_history WHERE user_id = ?",
                (user_id,),
            )
            next_order = cursor.fetchone()[0]
            cursor.execute(
                "INSERT OR IGNORE INTO user_history (user_id, item_idx, order_idx, added_at) "
                "VALUES (?, ?, ?, CURRENT_TIMESTAMP)",
                (user_id, item_idx, next_order),
            )
            conn.commit()
            return True
        except sqlite3.Error:
            log.exception(
                "Failed to add history item user=%s item=%d", username, item_idx
            )
            return False


def remove_history_item(username: str, item_idx: int) -> bool:
    with connection() as conn:
        cursor = conn.cursor()
        user_id = _get_user_id(cursor, username)
        if user_id is None:
            return False
        try:
            cursor.execute(
                "DELETE FROM user_history WHERE user_id = ? AND item_idx = ?",
                (user_id, item_idx),
            )
            conn.commit()
            return True
        except sqlite3.Error:
            log.exception(
                "Failed to remove history item user=%s item=%d", username, item_idx
            )
            return False


def clear_user_history(username: str) -> bool:
    with connection() as conn:
        cursor = conn.cursor()
        user_id = _get_user_id(cursor, username)
        if user_id is None:
            return False
        try:
            cursor.execute("DELETE FROM user_history WHERE user_id = ?", (user_id,))
            conn.commit()
            return True
        except sqlite3.Error:
            log.exception("Failed to clear history user=%s", username)
            return False


def log_recommendation(
    username: str | None,
    strategy: str,
    latency_ms: float,
    history: list[int],
    results: list[int],
    endpoint: str | None = None,
    status_code: int | None = None,
) -> bool:
    with connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO recommendation_logs
                    (username, strategy, latency_ms, history, results, endpoint, status_code)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    username,
                    strategy,
                    latency_ms,
                    ",".join(map(str, history)) if history else "",
                    ",".join(map(str, results)) if results else "",
                    endpoint,
                    status_code,
                ),
            )
            conn.commit()
            return True
        except sqlite3.Error:
            log.exception("Failed to log recommendation strategy=%s", strategy)
            return False


def _percentile(sorted_values: list[float], fraction: float) -> float:
    """Nearest-rank percentile over an already-sorted list.

    Nearest-rank (rather than interpolation) keeps the result an observed latency,
    which is what a latency SLO is usually stated against.
    """
    if not sorted_values:
        return 0.0
    rank = math.ceil(fraction * len(sorted_values))
    index = min(max(rank - 1, 0), len(sorted_values) - 1)
    return float(sorted_values[index])


def _summarize_latencies(values: list[float]) -> dict:
    """Latency summary. median and p50 are the same percentile by definition."""
    if not values:
        return {
            "count": 0,
            "avg": 0.0,
            "min": 0.0,
            "max": 0.0,
            "median": 0.0,
            "p50": 0.0,
            "p95": 0.0,
            "p99": 0.0,
        }
    values = sorted(values)
    p50 = _percentile(values, 0.50)
    return {
        "count": len(values),
        "avg": round(sum(values) / len(values), 2),
        "min": round(values[0], 2),
        "max": round(values[-1], 2),
        # median and p50 are deliberately the same value - see the API docs note.
        "median": round(p50, 2),
        "p50": round(p50, 2),
        "p95": round(_percentile(values, 0.95), 2),
        "p99": round(_percentile(values, 0.99), 2),
    }


def _fetch_latencies(hours: int, column: str | None = None) -> list[tuple]:
    """Latency rows inside the window, optionally grouped by a column."""
    selected = f"{column}, latency_ms" if column else "latency_ms"
    with connection() as conn:
        try:
            return conn.execute(
                f"SELECT {selected} FROM recommendation_logs "
                "WHERE timestamp >= datetime('now', ?)",
                (f"-{int(hours)} hours",),
            ).fetchall()
        except sqlite3.Error:
            log.exception("Failed to read recommendation latencies")
            return []


def get_latency_stats(hours: int = 24) -> dict:
    """Latency percentiles overall and broken down by endpoint and strategy."""
    overall = _summarize_latencies(
        [float(row["latency_ms"]) for row in _fetch_latencies(hours)]
    )

    breakdowns: dict[str, list[dict]] = {}
    for key, column in (("by_endpoint", "endpoint"), ("by_strategy", "strategy")):
        grouped: dict[str, list[float]] = {}
        for row in _fetch_latencies(hours, column):
            grouped.setdefault(row[column] or "unknown", []).append(
                float(row["latency_ms"])
            )
        breakdowns[key] = sorted(
            ({column: name, **_summarize_latencies(vals)} for name, vals in grouped.items()),
            key=lambda entry: -entry["count"],
        )

    return {"window_hours": hours, "overall": overall, **breakdowns}


def get_latency_timeseries(hours: int = 24) -> list[dict]:
    """Hourly latency buckets for the dashboard chart."""
    buckets: dict[str, list[float]] = {}
    with connection() as conn:
        try:
            rows = conn.execute(
                "SELECT strftime('%Y-%m-%dT%H:00', timestamp) AS bucket, latency_ms "
                "FROM recommendation_logs WHERE timestamp >= datetime('now', ?) "
                "ORDER BY bucket ASC",
                (f"-{int(hours)} hours",),
            ).fetchall()
        except sqlite3.Error:
            log.exception("Failed to read latency timeseries")
            return []

    for row in rows:
        buckets.setdefault(row["bucket"], []).append(float(row["latency_ms"]))

    return [
        {
            "bucket": bucket,
            "count": len(values),
            "avg": round(sum(values) / len(values), 2),
            "p95": round(_percentile(sorted(values), 0.95), 2),
        }
        for bucket, values in sorted(buckets.items())
    ]



def get_recommendation_logs(limit: int = 100) -> list[dict]:
    with connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM recommendation_logs ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        )
        return [dict(row) for row in cursor.fetchall()]


def cleanup_recommendation_logs(retention_days: int) -> int:
    with connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "DELETE FROM recommendation_logs WHERE timestamp < datetime('now', ?)",
                (f"-{retention_days} days",),
            )
            deleted = cursor.rowcount
            conn.commit()
            return deleted
        except sqlite3.Error:
            log.exception("Failed to cleanup recommendation logs")
            conn.rollback()
            return 0
