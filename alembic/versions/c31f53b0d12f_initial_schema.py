"""initial schema

Revision ID: c31f53b0d12f
Revises:
Create Date: 2026-07-26 16:22:48.470047

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c31f53b0d12f"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("username", sa.Text, unique=True, nullable=False),
        sa.Column("password_hash", sa.Text, nullable=False),
        sa.Column("role", sa.Text, nullable=False, server_default="learner"),
    )

    op.create_table(
        "user_history",
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

    op.create_table(
        "recommendation_logs",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("timestamp", sa.DateTime, server_default=sa.func.current_timestamp()),
        sa.Column("username", sa.Text, nullable=True),
        sa.Column("strategy", sa.Text, nullable=False),
        sa.Column("latency_ms", sa.Float, nullable=False),
        sa.Column("history", sa.Text, nullable=True),
        sa.Column("results", sa.Text, nullable=True),
    )


def downgrade() -> None:
    op.drop_table("recommendation_logs")
    op.drop_table("user_history")
    op.drop_table("users")
