from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

import bcrypt

from core.config import settings

log = logging.getLogger(__name__)

DB_PATH = Path("data/db.sqlite3")


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(
        plain_password.encode("utf-8"), hashed_password.encode("utf-8")
    )


def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    # Create users table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'learner'
    );
    """)

    # Create user_history table
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

    # Create recommendation_logs table
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

    # Seed default users if users table is empty
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

    conn.close()


# Helper queries
def get_user_by_username(username: str) -> dict | None:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return dict(row)
    return None


def create_user(username: str, password_hash: str, role: str = "learner") -> bool:
    conn = get_connection()
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
    finally:
        conn.close()


def get_user_history(username: str) -> list[int]:
    user = get_user_by_username(username)
    if not user:
        return []
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT item_idx FROM user_history WHERE user_id = ? ORDER BY order_idx ASC",
        (user["id"],),
    )
    rows = cursor.fetchall()
    conn.close()
    return [row["item_idx"] for row in rows]


def add_history_item(username: str, item_idx: int) -> bool:
    user = get_user_by_username(username)
    if not user:
        return False
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT COALESCE(MAX(order_idx), -1) + 1 FROM user_history WHERE user_id = ?",
            (user["id"],),
        )
        next_order = cursor.fetchone()[0]
        cursor.execute(
            "INSERT OR IGNORE INTO user_history (user_id, item_idx, order_idx, added_at) "
            "VALUES (?, ?, ?, CURRENT_TIMESTAMP)",
            (user["id"], item_idx, next_order),
        )
        conn.commit()
        return True
    except Exception:
        return False
    finally:
        conn.close()


def remove_history_item(username: str, item_idx: int) -> bool:
    user = get_user_by_username(username)
    if not user:
        return False
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "DELETE FROM user_history WHERE user_id = ? AND item_idx = ?",
            (user["id"], item_idx),
        )
        conn.commit()
        return True
    except Exception:
        return False
    finally:
        conn.close()


def clear_user_history(username: str) -> bool:
    user = get_user_by_username(username)
    if not user:
        return False
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM user_history WHERE user_id = ?", (user["id"],))
        conn.commit()
        return True
    except Exception:
        return False
    finally:
        conn.close()


def log_recommendation(
    username: str | None,
    strategy: str,
    latency_ms: float,
    history: list[int],
    results: list[int],
) -> bool:
    conn = get_connection()
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
    except Exception:
        return False
    finally:
        conn.close()


def get_recommendation_logs(limit: int = 100) -> list[dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM recommendation_logs ORDER BY timestamp DESC LIMIT ?", (limit,)
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]
