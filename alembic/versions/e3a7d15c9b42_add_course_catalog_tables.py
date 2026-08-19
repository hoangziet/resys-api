"""add course catalog tables (courses + courses_en)

Creates the localized course catalog:

* ``courses``    - French catalog, seeded from ``item_metadata.csv``. This is the
  language the recommender itself was trained on; it stays the reference row set.
* ``courses_en`` - English translations for display, seeded from
  ``item_en_final.csv``, keyed by the same ``item_idx`` (FK -> ``courses``) so the
  mapping to the existing catalog and to ``user_history.item_idx`` is preserved.
  Also carries ``thumbnail_path``, the per-course thumbnail image URL.

``core.database.init_db`` creates the same two tables with ``CREATE TABLE IF NOT
EXISTS`` for fresh local runs, so this revision skips any table that already
exists instead of failing.

Revision ID: e3a7d15c9b42
Revises: a0882f19c5b2
Create Date: 2026-08-19 16:10:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import context, op

# revision identifiers, used by Alembic.
revision: str = "e3a7d15c9b42"
down_revision: str | Sequence[str] | None = "a0882f19c5b2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _missing_table(name: str) -> bool:
    """True when the table should be created.

    Offline (--sql) mode has no live connection to inspect, so emit the CREATE
    unconditionally there.
    """
    if context.is_offline_mode():
        return True
    return not sa.inspect(op.get_bind()).has_table(name)


def upgrade() -> None:
    if _missing_table("courses"):
        op.create_table(
            "courses",
            sa.Column("item_idx", sa.Integer, primary_key=True, autoincrement=False, nullable=False),
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

    if _missing_table("courses_en"):
        op.create_table(
            "courses_en",
            sa.Column(
                "item_idx",
                sa.Integer,
                sa.ForeignKey("courses.item_idx", ondelete="CASCADE"),
                primary_key=True,
                autoincrement=False,
                nullable=False,
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


def downgrade() -> None:
    if not _missing_table("courses_en"):
        op.drop_table("courses_en")
    if not _missing_table("courses"):
        op.drop_table("courses")
