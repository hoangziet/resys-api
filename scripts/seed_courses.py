"""Import the French and English course catalogs from CSV into SQLite.

``core.database.init_db`` already seeds both tables on startup; this script is for
re-importing after the CSVs change.

    python -m scripts.seed_courses            # only seeds tables whose row count differs
    python -m scripts.seed_courses --force    # re-import every row
"""

from __future__ import annotations

import argparse
import logging
import sys

from core.catalog_seed import seed_courses
from core.database import get_connection, init_db


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-import every row even when the row counts already match",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    # Make sure the tables exist before seeding into them.
    init_db()

    conn = get_connection()
    try:
        cursor = conn.cursor()
        seeded = seed_courses(cursor, force=args.force)
        conn.commit()

        for table in ("courses", "courses_en"):
            total = cursor.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            print(f"{table}: {total} rows total ({seeded.get(table, 0)} written)")
    finally:
        conn.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
