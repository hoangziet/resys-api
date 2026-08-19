from __future__ import annotations

import contextlib
import logging
import sqlite3
from collections.abc import Generator

import bcrypt

from core.catalog_seed import fetch_courses, seed_courses
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
        duration REAL
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


def _escape_like(value: str) -> str:
    """Escape LIKE wildcards so user input is matched literally."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


# Columns returned by the paginated course query, aliased so both languages look
# identical to the serializer.
_COURSE_SELECT_COLUMNS = (
    "c.item_idx",
    "c.item_id",
    "c.title",
    "c.description",
    "c.language",
    "c.difficulty",
    "c.theme",
    "c.software",
    "c.job",
    "c.type",
    "c.duration",
)


def _build_course_filters(
    lang: str, q: str | None, facets: dict[str, list[str]]
) -> tuple[str, list, str | None]:
    """Build the shared WHERE clause for the course query and its COUNT twin.

    Each facet group contributes one EXISTS, so groups AND together; the IN inside
    a group makes its values OR together. An empty group adds no clause at all.
    """
    clauses: list[str] = []
    params: list = []
    like: str | None = None

    if q and q.strip():
        like = f"%{_escape_like(q.strip())}%"
        clauses.append(
            "(c.title LIKE ? ESCAPE '\\' OR c.description LIKE ? ESCAPE '\\')"
        )
        params.extend([like, like])

    for kind, slugs in facets.items():
        if not slugs:
            continue
        placeholders = ", ".join("?" for _ in slugs)
        clauses.append(
            "EXISTS (SELECT 1 FROM course_facets f "
            "WHERE f.item_idx = c.item_idx AND f.kind = ? AND f.lang = ? "
            f"AND f.slug IN ({placeholders}))"
        )
        params.extend([kind, lang, *slugs])

    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    return where, params, like


def query_courses(
    *,
    lang: str = "en",
    q: str | None = None,
    facets: dict[str, list[str]] | None = None,
    page: int = 1,
    limit: int = 12,
) -> tuple[list[dict], int]:
    """Filter and paginate courses entirely in SQL.

    Returns ``(rows, total)`` where ``rows`` holds at most ``limit`` records and
    ``total`` is the number of courses matching the filters, ignoring pagination.
    """
    facets = facets or {}
    if lang == "en":
        source = "courses_en c"
        thumbnail = "c.thumbnail_path AS thumbnail_path"
    else:
        # Thumbnails live on courses_en but are language-neutral.
        source = "courses c LEFT JOIN courses_en en ON en.item_idx = c.item_idx"
        thumbnail = "en.thumbnail_path AS thumbnail_path"

    where, where_params, like = _build_course_filters(lang, q, facets)
    columns = ", ".join([*_COURSE_SELECT_COLUMNS, thumbnail])

    # Title matches first (mirrors the previous in-memory ranking), then item_idx
    # so paging is stable.
    if like is None:
        order_by = " ORDER BY c.item_idx"
        order_params: list = []
    else:
        order_by = " ORDER BY CASE WHEN c.title LIKE ? ESCAPE '\\' THEN 0 ELSE 1 END, c.item_idx"
        order_params = [like]

    offset = (page - 1) * limit

    with connection() as conn:
        cursor = conn.cursor()
        try:
            total = int(
                cursor.execute(
                    f"SELECT COUNT(*) FROM {source}{where}", where_params
                ).fetchone()[0]
            )
            rows = cursor.execute(
                f"SELECT {columns} FROM {source}{where}{order_by} LIMIT ? OFFSET ?",
                [*where_params, *order_params, limit, offset],
            ).fetchall()
            return [dict(row) for row in rows], total
        except sqlite3.Error:
            log.exception("Failed to query courses lang=%s facets=%s", lang, facets)
            return [], 0


def get_facet_options(lang: str = "en") -> list[dict]:
    """Distinct filter values for a language, with the number of matching courses.

    Grouped by slug rather than label so a slug collision surfaces as one option
    instead of two identical-looking ones.
    """
    with connection() as conn:
        cursor = conn.cursor()
        try:
            rows = cursor.execute(
                "SELECT kind, slug, MIN(label) AS label, COUNT(DISTINCT item_idx) AS count "
                "FROM course_facets WHERE lang = ? GROUP BY kind, slug",
                (lang,),
            ).fetchall()
            return [dict(row) for row in rows]
        except sqlite3.Error:
            log.exception("Failed to read facet options lang=%s", lang)
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
) -> bool:
    with connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO recommendation_logs (username, strategy, latency_ms, history, results)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    username,
                    strategy,
                    latency_ms,
                    ",".join(map(str, history)) if history else "",
                    ",".join(map(str, results)) if results else "",
                ),
            )
            conn.commit()
            return True
        except sqlite3.Error:
            log.exception("Failed to log recommendation strategy=%s", strategy)
            return False


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
