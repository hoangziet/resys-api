from __future__ import annotations

import csv
import logging
import sqlite3
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
        return seeded

    seeded["courses_en"] = _seed_table(
        cursor,
        "courses_en",
        settings.courses_csv_en,
        EN_COLUMNS,
        default_language="en",
        force=force,
    )
    return seeded


def fetch_courses(cursor: sqlite3.Cursor, table: str) -> Iterable[sqlite3.Row]:
    columns = EN_COLUMNS if table == "courses_en" else FR_COLUMNS
    quoted = ", ".join(f'"{column}"' for column in columns)
    return cursor.execute(f"SELECT {quoted} FROM {table}")
