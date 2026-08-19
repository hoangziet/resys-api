"""add course_facets table

``courses.theme`` / ``software`` / ``job`` are multilabel: a single column holds a
comma-separated list (``"Collaborer, Communiquer, Partager"``), and ``difficulty``
can too. Neither ``=`` nor ``LIKE '%…%'`` filters those correctly - ``LIKE '%Teams%'``
also matches the distinct token ``Skype VS Teams``, and ``LIKE '%Forms%'`` also
matches ``Microsoft Forms``.

``course_facets`` splits those columns into one row per (course, facet value), which
gives exact-token equality, an indexed lookup for filtering, and the distinct-value
list the filter UI needs. It is pure derived data: ``courses`` / ``courses_en`` remain
the source of truth and ``core.catalog_seed`` rebuilds this table from them.

``core.database.init_db`` creates the same table with ``CREATE TABLE IF NOT EXISTS``,
so this revision skips creation when it already exists.

Revision ID: b6d41e70c9a5
Revises: e3a7d15c9b42
Create Date: 2026-08-19 18:05:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import context, op

# revision identifiers, used by Alembic.
revision: str = "b6d41e70c9a5"
down_revision: str | Sequence[str] | None = "e3a7d15c9b42"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _missing_table(name: str) -> bool:
    """True when the table should be created (offline mode cannot inspect)."""
    if context.is_offline_mode():
        return True
    return not sa.inspect(op.get_bind()).has_table(name)


def upgrade() -> None:
    if not _missing_table("course_facets"):
        return

    op.create_table(
        "course_facets",
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
    )
    op.create_index(
        "ix_course_facets_lookup", "course_facets", ["kind", "lang", "slug"]
    )


def downgrade() -> None:
    if _missing_table("course_facets"):
        return
    op.drop_index("ix_course_facets_lookup", table_name="course_facets")
    op.drop_table("course_facets")
