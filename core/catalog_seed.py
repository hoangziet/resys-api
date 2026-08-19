from __future__ import annotations

import csv
import logging
import re
import sqlite3
import unicodedata
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

from core.config import settings

log = logging.getLogger(__name__)

# Columns shared by both catalog tables, in insert order.
_BASE_COLUMNS: tuple[str, ...] = (
    "item_idx",
    "item_id",
    "title",
    "description",
    "text",
    "language",
    "difficulty",
    "theme",
    "software",
    "job",
    "type",
    "duration",
)
FR_COLUMNS: tuple[str, ...] = _BASE_COLUMNS
EN_COLUMNS: tuple[str, ...] = (*_BASE_COLUMNS, "thumbnail_path")

# Course columns that hold a comma-separated list of values and get split into
# course_facets rows. "job" is exposed to clients as "job_type".
FACET_COLUMNS: tuple[str, ...] = ("difficulty", "theme", "software", "job", "type")

# difficulty is stored as "<level> - <label>" in both catalogs ("1 - Découverte",
# "1 - Beginner"). Keying its slug off the stable level digit instead of the
# translated label makes difficulty filters language-independent.
DIFFICULTY_SLUGS: dict[str, str] = {
    "1": "beginner",
    "2": "intermediate",
    "3": "advanced",
}

# Canonical stored label for an admin-supplied difficulty slug. Written to both
# catalogs so facet_slug() derives the same slug back out.
DIFFICULTY_LABELS: dict[str, str] = {
    "beginner": "1 - Beginner",
    "intermediate": "2 - Intermediate",
    "advanced": "3 - Advanced",
}

_SLUG_STRIP_RE = re.compile(r"[^a-z0-9]+")


def parse_float(value: str | None) -> float | None:
    """Coerce a CSV cell to float, mirroring ItemEmbeddings._parse_float.

    Duplicated rather than imported from models.embeddings on purpose: that module
    loads the sentence-embedding checkpoint at import time, and the database layer
    must not pull torch in just to seed a table.
    """
    if value is None or value == "":
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _clean(value: str | None) -> str | None:
    """Normalize a CSV cell: blank becomes NULL, everything else is stripped."""
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def read_course_rows(
    path: Path, columns: Sequence[str], default_language: str
) -> list[tuple[Any, ...]]:
    """Read a course CSV into row tuples ordered to match ``columns``.

    ``item_en_final.csv`` is written with a UTF-8 BOM, hence ``utf-8-sig``.
    Rows without a usable integer ``item_idx`` are skipped.
    """
    rows: list[tuple[Any, ...]] = []
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            try:
                item_idx = int(str(row.get("item_idx", "")).strip())
            except (TypeError, ValueError):
                continue

            values: list[Any] = []
            for column in columns:
                if column == "item_idx":
                    values.append(item_idx)
                elif column == "duration":
                    values.append(parse_float(row.get("duration")))
                elif column == "title":
                    # NOT NULL in both tables; empty string is acceptable, NULL is not.
                    values.append(_clean(row.get("title")) or "")
                elif column == "language":
                    values.append(_clean(row.get("language")) or default_language)
                else:
                    values.append(_clean(row.get(column)))
            rows.append(tuple(values))
    return rows


def _upsert_sql(table: str, columns: Sequence[str]) -> str:
    """Build an idempotent upsert keyed on item_idx.

    ON CONFLICT DO UPDATE rather than INSERT OR REPLACE: REPLACE deletes the
    conflicting row first, which would fire courses_en's ON DELETE CASCADE and
    silently wipe the English rows whenever the French table is re-seeded.
    """
    quoted = ", ".join(f'"{column}"' for column in columns)
    placeholders = ", ".join("?" for _ in columns)
    updates = ", ".join(
        f'"{column}" = excluded."{column}"' for column in columns if column != "item_idx"
    )
    return (
        f"INSERT INTO {table} ({quoted}) VALUES ({placeholders}) "
        f'ON CONFLICT("item_idx") DO UPDATE SET {updates}'
    )


def _row_count(cursor: sqlite3.Cursor, table: str) -> int:
    return int(cursor.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])


def _seed_table(
    cursor: sqlite3.Cursor,
    table: str,
    csv_path: Path,
    columns: Sequence[str],
    default_language: str,
    force: bool,
) -> int:
    if not csv_path.exists():
        log.warning("Course CSV not found, skipping %s seed: %s", table, csv_path)
        return 0

    rows = read_course_rows(csv_path, columns, default_language)
    if not rows:
        log.warning("Course CSV %s has no usable rows, skipping %s seed", csv_path, table)
        return 0

    existing = _row_count(cursor, table)
    if not force and existing == len(rows):
        log.debug("%s already holds %d rows, skipping seed", table, existing)
        return 0

    cursor.executemany(_upsert_sql(table, columns), rows)
    log.info("Seeded %s: %d rows from %s (was %d)", table, len(rows), csv_path, existing)
    return len(rows)


def seed_courses(cursor: sqlite3.Cursor, *, force: bool = False) -> dict[str, int]:
    """Import the French and English catalogs from CSV into SQLite.

    Idempotent: a table whose row count already matches its CSV is left alone
    unless ``force`` is set. ``courses`` is seeded first because
    ``courses_en.item_idx`` is a foreign key into it and PRAGMA foreign_keys is ON.
    The caller owns the transaction (commit).
    """
    seeded = {
        "courses": _seed_table(
            cursor,
            "courses",
            settings.courses_csv_fr,
            FR_COLUMNS,
            default_language="fr",
            force=force,
        )
    }

    if _row_count(cursor, "courses") == 0:
        log.warning(
            "courses is empty, skipping courses_en seed to avoid foreign key violations"
        )
        seeded["courses_en"] = 0
        seeded["course_facets"] = 0
        return seeded

    seeded["courses_en"] = _seed_table(
        cursor,
        "courses_en",
        settings.courses_csv_en,
        EN_COLUMNS,
        default_language="en",
        force=force,
    )

    # course_facets is derived entirely from the two tables above, so rebuild it
    # whenever either was written, or whenever it is empty.
    if seeded["courses"] or seeded["courses_en"] or _row_count(cursor, "course_facets") == 0:
        seeded["course_facets"] = rebuild_course_facets(cursor)
    else:
        seeded["course_facets"] = 0
    return seeded


def slugify(label: str) -> str:
    """Turn a facet label into a stable URL-safe token.

    "Power Automate - Flow" -> power_automate_flow
    "Téléphonie & Visio"    -> telephonie_visio
    """
    decomposed = unicodedata.normalize("NFKD", label)
    ascii_only = decomposed.encode("ascii", "ignore").decode("ascii")
    return _SLUG_STRIP_RE.sub("_", ascii_only.lower()).strip("_")


def facet_slug(kind: str, label: str) -> str | None:
    """Slug for one facet value, or None when the label yields nothing usable."""
    if kind == "difficulty":
        level = label.strip()[:1]
        slug = DIFFICULTY_SLUGS.get(level)
        if slug:
            return slug
        # Unexpected difficulty format: fall through to generic slugging rather
        # than dropping the value silently.
        log.warning("Unrecognized difficulty label %r, slugging generically", label)
    return slugify(label) or None


def split_facet_values(raw: str | None) -> list[str]:
    """Split a multilabel column into its individual labels."""
    if not raw:
        return []
    return [part.strip() for part in raw.split(",") if part.strip()]


_FACET_INSERT_SQL = (
    "INSERT OR REPLACE INTO course_facets "
    '("item_idx", "kind", "lang", "slug", "label") VALUES (?, ?, ?, ?, ?)'
)


def _facet_rows_for(
    row: sqlite3.Row, lang: str, seen_slugs: dict[tuple[str, str, str], str] | None = None
) -> list[tuple[Any, ...]]:
    """Expand one course row into its course_facets rows."""
    item_idx = int(row["item_idx"])
    rows: list[tuple[Any, ...]] = []
    for kind in FACET_COLUMNS:
        for label in split_facet_values(row[kind]):
            slug = facet_slug(kind, label)
            if slug is None:
                continue

            # Two different labels collapsing to one slug would silently merge
            # distinct filter values - surface it instead.
            if seen_slugs is not None:
                key = (kind, lang, slug)
                previous = seen_slugs.get(key)
                if previous is None:
                    seen_slugs[key] = label
                elif previous != label and kind != "difficulty":
                    log.warning(
                        "Facet slug collision: %s/%s slug %r from both %r and %r",
                        kind,
                        lang,
                        slug,
                        previous,
                        label,
                    )
            rows.append((item_idx, kind, lang, slug, label))
    return rows


def _facet_select_sql(table: str, where: str = "") -> str:
    quoted = ", ".join(f'"{column}"' for column in FACET_COLUMNS)
    return f'SELECT "item_idx", {quoted} FROM {table}{where}'


def rebuild_facets_for_item(cursor: sqlite3.Cursor, item_idx: int) -> int:
    """Rebuild course_facets for a single course, after a create or update.

    Cheaper than a full rebuild and enough for admin CRUD, since facets for one
    course depend only on that course's rows. The caller commits.
    """
    cursor.execute("DELETE FROM course_facets WHERE item_idx = ?", (item_idx,))

    rows: list[tuple[Any, ...]] = []
    for table, lang in (("courses", "fr"), ("courses_en", "en")):
        row = cursor.execute(
            _facet_select_sql(table, " WHERE item_idx = ?"), (item_idx,)
        ).fetchone()
        if row is not None:
            rows += _facet_rows_for(row, lang)

    if rows:
        cursor.executemany(_FACET_INSERT_SQL, rows)
    return len(rows)


def rebuild_course_facets(cursor: sqlite3.Cursor) -> int:
    """Rebuild course_facets from courses (fr) and courses_en (en).

    Full DELETE + insert: facets are pure derived data, so rebuilding is always
    safe and stops them drifting from the course tables. The caller commits.
    """
    cursor.execute("DELETE FROM course_facets")

    rows: list[tuple[Any, ...]] = []
    seen_slugs: dict[tuple[str, str, str], str] = {}

    for table, lang in (("courses", "fr"), ("courses_en", "en")):
        for row in cursor.execute(_facet_select_sql(table)).fetchall():
            rows += _facet_rows_for(row, lang, seen_slugs)

    if not rows:
        log.warning("No course facets derived; course tables may be empty")
        return 0

    cursor.executemany(_FACET_INSERT_SQL, rows)
    log.info(
        "Rebuilt course_facets: %d rows, %d distinct (kind, lang, slug)",
        len(rows),
        len(seen_slugs),
    )
    return len(rows)


def fetch_courses(cursor: sqlite3.Cursor, table: str) -> Iterable[sqlite3.Row]:
    columns = EN_COLUMNS if table == "courses_en" else FR_COLUMNS
    quoted = ", ".join(f'"{column}"' for column in columns)
    return cursor.execute(f"SELECT {quoted} FROM {table}")
