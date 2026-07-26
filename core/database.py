from __future__ import annotations

import contextlib
import logging
import sqlite3
from collections.abc import Generator
from pathlib import Path

import bcrypt

from core.config import settings

log = logging.getLogger(__name__)

DB_PATH = Path("data/db.sqlite3")

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
    return bcrypt.checkpw(
        plain_password.encode("utf-8"), hashed_password.encode("utf-8")
    )


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

    conn.commit()

    cursor.execute("SELECT COUNT(*) as count FROM users")
    if cursor.fetchone()["count"] == 0:
        cursor.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
            (
                settings.learner_username,
                hash_password(settings.learner_password),
                "learner",
            ),
        )
        cursor.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
            (settings.admin_username, hash_password(settings.admin_password), "admin"),
        )
        conn.commit()
        log.info(
            "Seeded database with users: %s (learner), %s (admin)",
            settings.learner_username,
            settings.admin_username,
        )

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
