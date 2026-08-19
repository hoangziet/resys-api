"""add monitoring columns and course embedding_status

Two additions:

* ``recommendation_logs.endpoint`` / ``status_code`` - written by
  ``core.monitoring.RecommendationMetricsMiddleware`` so latency percentiles cover
  failed and rate-limited requests, not only successful ones.
* ``courses.embedding_status`` - ``'ready'`` when the course has a row in the text
  embedding tensor, ``'pending'`` for admin-created courses awaiting the offline
  embedding job. Text-similarity recommendations skip pending courses.

Every column is added defensively because ``core.database.init_db`` also creates
these tables (and back-fills the same columns via ``_ensure_sqlite_columns``) for
databases that predate this revision.

Revision ID: c8f2a4b91d63
Revises: b6d41e70c9a5
Create Date: 2026-08-19 20:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import context, op

# revision identifiers, used by Alembic.
revision: str = "c8f2a4b91d63"
down_revision: str | Sequence[str] | None = "b6d41e70c9a5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _columns(table: str) -> set[str]:
    if context.is_offline_mode():
        return set()
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table(table):
        return set()
    return {column["name"] for column in inspector.get_columns(table)}


def _indexes(table: str) -> set[str]:
    if context.is_offline_mode():
        return set()
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table(table):
        return set()
    return {index["name"] for index in inspector.get_indexes(table)}


def upgrade() -> None:
    log_columns = _columns("recommendation_logs")
    if "endpoint" not in log_columns:
        op.add_column(
            "recommendation_logs", sa.Column("endpoint", sa.Text, nullable=True)
        )
    if "status_code" not in log_columns:
        op.add_column(
            "recommendation_logs", sa.Column("status_code", sa.Integer, nullable=True)
        )
    if "ix_rec_logs_endpoint" not in _indexes("recommendation_logs"):
        op.create_index("ix_rec_logs_endpoint", "recommendation_logs", ["endpoint"])

    if "embedding_status" not in _columns("courses"):
        op.add_column(
            "courses",
            sa.Column(
                "embedding_status", sa.Text, nullable=True, server_default="ready"
            ),
        )
        # Everything already in the catalog came from the CSV, so it has an
        # embedding row; only courses created after this point are pending.
        op.execute("UPDATE courses SET embedding_status = 'ready'")


def downgrade() -> None:
    if "embedding_status" in _columns("courses"):
        with op.batch_alter_table("courses") as batch_op:
            batch_op.drop_column("embedding_status")

    if "ix_rec_logs_endpoint" in _indexes("recommendation_logs"):
        op.drop_index("ix_rec_logs_endpoint", table_name="recommendation_logs")

    log_columns = _columns("recommendation_logs")
    with op.batch_alter_table("recommendation_logs") as batch_op:
        if "status_code" in log_columns:
            batch_op.drop_column("status_code")
        if "endpoint" in log_columns:
            batch_op.drop_column("endpoint")
