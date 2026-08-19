from __future__ import annotations

import sqlalchemy as sa

metadata = sa.MetaData()

# Single-column INTEGER PRIMARY KEY columns are declared nullable=True on purpose.
# In SQLite such a column is a rowid alias, and core/database.py creates these
# tables with raw DDL that omits an explicit NOT NULL, so PRAGMA table_info reports
# notnull=0 and SQLAlchemy reflects the column as nullable. primary_key=True alone
# would imply nullable=False here and make `alembic check` (CI: ci-cd.yml) fail with
# a modify_nullable drift that no migration can resolve. Do not "tidy" these away.

users = sa.Table(
    "users",
    metadata,
    sa.Column("id", sa.Integer, primary_key=True, autoincrement=True, nullable=True),
    sa.Column("username", sa.Text, unique=True, nullable=False),
    sa.Column("password_hash", sa.Text, nullable=False),
    sa.Column("role", sa.Text, nullable=False, server_default="learner"),
)

user_history = sa.Table(
    "user_history",
    metadata,
    sa.Column(
        "user_id",
        sa.Integer,
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    ),
    sa.Column("item_idx", sa.Integer, nullable=False),
    sa.Column("order_idx", sa.Integer, nullable=False, server_default="0"),
    sa.Column("added_at", sa.DateTime, server_default=sa.func.current_timestamp()),
    sa.PrimaryKeyConstraint("user_id", "item_idx"),
)

courses = sa.Table(
    "courses",
    metadata,
    sa.Column("item_idx", sa.Integer, primary_key=True, autoincrement=False, nullable=True),
    sa.Column("item_id", sa.Text, nullable=True),
    sa.Column("title", sa.Text, nullable=False),
    sa.Column("description", sa.Text, nullable=True),
    sa.Column("text", sa.Text, nullable=True),
    sa.Column("language", sa.Text, nullable=True, server_default="fr"),
    sa.Column("difficulty", sa.Text, nullable=True),
    sa.Column("theme", sa.Text, nullable=True),
    sa.Column("software", sa.Text, nullable=True),
    sa.Column("job", sa.Text, nullable=True),
    sa.Column("type", sa.Text, nullable=True),
    sa.Column("duration", sa.Float, nullable=True),
)

courses_en = sa.Table(
    "courses_en",
    metadata,
    sa.Column(
        "item_idx",
        sa.Integer,
        sa.ForeignKey("courses.item_idx", ondelete="CASCADE"),
        primary_key=True,
        autoincrement=False,
        nullable=True,
    ),
    sa.Column("item_id", sa.Text, nullable=True),
    sa.Column("title", sa.Text, nullable=False),
    sa.Column("description", sa.Text, nullable=True),
    sa.Column("text", sa.Text, nullable=True),
    sa.Column("language", sa.Text, nullable=True, server_default="en"),
    sa.Column("difficulty", sa.Text, nullable=True),
    sa.Column("theme", sa.Text, nullable=True),
    sa.Column("software", sa.Text, nullable=True),
    sa.Column("job", sa.Text, nullable=True),
    sa.Column("type", sa.Text, nullable=True),
    sa.Column("duration", sa.Float, nullable=True),
    sa.Column("thumbnail_path", sa.Text, nullable=True),
)

course_facets = sa.Table(
    "course_facets",
    metadata,
    sa.Column(
        "item_idx",
        sa.Integer,
        sa.ForeignKey("courses.item_idx", ondelete="CASCADE"),
        nullable=False,
    ),
    sa.Column("kind", sa.Text, nullable=False),
    sa.Column("lang", sa.Text, nullable=False),
    sa.Column("slug", sa.Text, nullable=False),
    sa.Column("label", sa.Text, nullable=False),
    sa.PrimaryKeyConstraint("item_idx", "kind", "lang", "slug"),
    sa.Index("ix_course_facets_lookup", "kind", "lang", "slug"),
)

recommendation_logs = sa.Table(
    "recommendation_logs",
    metadata,
    sa.Column("id", sa.Integer, primary_key=True, autoincrement=True, nullable=True),
    sa.Column("timestamp", sa.DateTime, server_default=sa.func.current_timestamp()),
    sa.Column("username", sa.Text, nullable=True),
    sa.Column("strategy", sa.Text, nullable=False),
    sa.Column("latency_ms", sa.FLOAT, nullable=False),
    sa.Column("history", sa.Text, nullable=True),
    sa.Column("results", sa.Text, nullable=True),
    sa.Index("ix_rec_logs_timestamp", "timestamp"),
    sa.Index("ix_rec_logs_username", "username"),
    sa.Index("ix_rec_logs_strategy", "strategy"),
)
