from __future__ import annotations

import sqlalchemy as sa

metadata = sa.MetaData()

users = sa.Table(
    "users",
    metadata,
    sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
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

recommendation_logs = sa.Table(
    "recommendation_logs",
    metadata,
    sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("timestamp", sa.DateTime, server_default=sa.func.current_timestamp()),
    sa.Column("username", sa.Text, nullable=True),
    sa.Column("strategy", sa.Text, nullable=False),
    sa.Column("latency_ms", sa.Float, nullable=False),
    sa.Column("history", sa.Text, nullable=True),
    sa.Column("results", sa.Text, nullable=True),
)
