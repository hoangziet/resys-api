"""Course search engine.

The Courses page pipeline lives here, deliberately separate from the recommender:

    Search query -> Search engine -> Course catalog -> Filter -> Pagination

This module must never import ``models.embeddings``, ``models.bert4rec`` or
``inference``. Course browsing is answered purely from the ``courses`` /
``courses_en`` / ``course_facets`` tables, so it works for every catalog row -
including courses the recommender does not know about yet.

Search, filtering and pagination all happen in SQL: only the requested page of
rows ever leaves the database.
"""

from __future__ import annotations

import logging
import math
import sqlite3

from core.database import connection

log = logging.getLogger(__name__)

# Columns a free-text query is matched against.
SEARCH_COLUMNS = ("title", "description", "theme", "software", "job")

# Columns returned for each course, aliased so both languages look identical to
# the serializer in models/catalog.py.
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

DEFAULT_LIMIT = 12
MAX_LIMIT = 100


def escape_like(value: str) -> str:
    """Escape LIKE wildcards so user input is matched literally."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def tokenize(q: str | None) -> list[str]:
    """Split a query into search tokens.

    "python machine learning" -> ["python", "machine", "learning"]
    """
    if not q:
        return []
    return [token for token in q.split() if token]


def _source_and_thumbnail(lang: str) -> tuple[str, str]:
    if lang == "en":
        return "courses_en c", "c.thumbnail_path AS thumbnail_path"
    # Thumbnails live on courses_en but are language-neutral.
    return (
        "courses c LEFT JOIN courses_en en ON en.item_idx = c.item_idx",
        "en.thumbnail_path AS thumbnail_path",
    )


def _token_clause() -> str:
    """One token must match at least one searchable column."""
    return "(" + " OR ".join(f"c.{col} LIKE ? ESCAPE '\\'" for col in SEARCH_COLUMNS) + ")"


def build_filters(
    lang: str, tokens: list[str], facets: dict[str, list[str]]
) -> tuple[str, list]:
    """Build the WHERE clause shared by the page query and its COUNT twin.

    Every token must match somewhere (AND across tokens, OR across columns), and
    each facet group contributes one EXISTS so groups AND together while the IN
    inside a group makes its values OR together. An omitted filter adds nothing.
    """
    clauses: list[str] = []
    params: list = []

    for token in tokens:
        like = f"%{escape_like(token)}%"
        clauses.append(_token_clause())
        params.extend([like] * len(SEARCH_COLUMNS))

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
    return where, params


def _order_by(tokens: list[str]) -> tuple[str, list]:
    """Rank title matches above body-only matches, then item_idx for stable paging."""
    if not tokens:
        return " ORDER BY c.item_idx", []

    scores = " + ".join(
        "CASE WHEN c.title LIKE ? ESCAPE '\\' THEN 1 ELSE 0 END" for _ in tokens
    )
    params = [f"%{escape_like(token)}%" for token in tokens]
    return f" ORDER BY ({scores}) DESC, c.item_idx", params


def search_courses(
    *,
    lang: str = "en",
    q: str | None = None,
    facets: dict[str, list[str]] | None = None,
    page: int = 1,
    limit: int = DEFAULT_LIMIT,
) -> tuple[list[dict], int]:
    """Search + filter + paginate, entirely in SQL.

    Returns ``(rows, total)`` where ``rows`` holds at most ``limit`` records and
    ``total`` counts every course matching the query and filters.
    """
    facets = facets or {}
    tokens = tokenize(q)
    source, thumbnail = _source_and_thumbnail(lang)
    where, where_params = build_filters(lang, tokens, facets)
    order_by, order_params = _order_by(tokens)
    columns = ", ".join([*_COURSE_SELECT_COLUMNS, thumbnail])
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
            log.exception("Course search failed lang=%s q=%r facets=%s", lang, q, facets)
            return [], 0


def total_pages(total: int, limit: int) -> int:
    return math.ceil(total / limit) if total and limit > 0 else 0


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
