from __future__ import annotations

import logging
from typing import Any

from core import database
from models.embeddings import item_embeddings

log = logging.getLogger(__name__)

DEFAULT_THUMBNAIL_URL = "/assets/thumbnail.png"
VIDEO_URL = "/assets/video.mp4"

SUPPORTED_LANGUAGES = ("en", "fr")
DEFAULT_LANGUAGE = "en"

# Fields returned to clients, in addition to thumbnail_url / video_url.
SERIALIZED_FIELDS = (
    "item_idx",
    "item_id",
    "title",
    "description",
    "language",
    "difficulty",
    "theme",
    "software",
    "job",
    "type",
    "duration",
)


class CourseCatalog:
    """Localized course text for display, read from SQLite.

    This is strictly a presentation layer. It never decides *which* items are
    returned or in what order - callers pass item_idx values that came from the
    model layer (models.embeddings / inference), which stays French-only so the
    English translations cannot influence BERT4Rec input or vector similarity.
    """

    def __init__(self) -> None:
        self._by_lang: dict[str, dict[int, dict[str, Any]]] = {}
        self._loaded = False

    def load(self) -> None:
        """Read every catalog table into memory. Safe to call repeatedly."""
        by_lang: dict[str, dict[int, dict[str, Any]]] = {}
        for lang in SUPPORTED_LANGUAGES:
            rows = database.get_courses(lang)
            by_lang[lang] = {int(row["item_idx"]): row for row in rows}
            log.info("Loaded %d courses for lang=%s", len(by_lang[lang]), lang)
        self._by_lang = by_lang
        self._loaded = True

    def _ensure_loaded(self) -> None:
        if not self._loaded:
            self.load()

    @staticmethod
    def normalize_lang(lang: str | None) -> str:
        return lang if lang in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE

    def _thumbnail_url(self, item_idx: int) -> str:
        """Thumbnails live on courses_en but are language-neutral."""
        row = self._by_lang.get("en", {}).get(item_idx)
        if row:
            path = row.get("thumbnail_path")
            if path and str(path).strip():
                return str(path).strip()
        return DEFAULT_THUMBNAIL_URL

    def _row_for(self, item_idx: int, lang: str) -> dict[str, Any] | None:
        row = self._by_lang.get(lang, {}).get(item_idx)
        if row is not None:
            return row
        # Partially seeded database: fall back to the other language, then to the
        # French CSV the model layer already holds, so a request degrades in
        # content rather than failing.
        for other in SUPPORTED_LANGUAGES:
            if other != lang:
                row = self._by_lang.get(other, {}).get(item_idx)
                if row is not None:
                    return row
        return item_embeddings.metadata.get(item_idx)

    def serialize_row(
        self, row: dict[str, Any], item_idx: int, *, thumbnail_path: str | None = None
    ) -> dict[str, Any]:
        """Map one catalog row to the API shape.

        Shared by the in-memory path (history, recommendations) and the SQL-backed
        course list, so the two can't drift apart. ``thumbnail_path`` lets a SQL row
        supply its own thumbnail instead of the in-memory lookup.
        """
        item: dict[str, Any] = {}
        for field in SERIALIZED_FIELDS:
            value = row.get(field)
            if field == "item_idx":
                item[field] = item_idx
            elif field == "duration":
                item[field] = value
            else:
                item[field] = "" if value is None else value

        if thumbnail_path is not None and str(thumbnail_path).strip():
            item["thumbnail_url"] = str(thumbnail_path).strip()
        else:
            item["thumbnail_url"] = self._thumbnail_url(item_idx)
        item["video_url"] = VIDEO_URL
        return item

    def serialize_query_row(self, row: dict[str, Any]) -> dict[str, Any]:
        """Serialize a row returned by core.database.query_courses."""
        return self.serialize_row(
            row,
            int(row["item_idx"]),
            thumbnail_path=row.get("thumbnail_path"),
        )

    def serialize_item(self, item_idx: int, lang: str = DEFAULT_LANGUAGE) -> dict[str, Any]:
        self._ensure_loaded()
        lang = self.normalize_lang(lang)
        row = self._row_for(item_idx, lang)
        if row is None:
            raise KeyError(f"Unknown item_idx: {item_idx}")
        return self.serialize_row(row, item_idx)

    def serialize_items(
        self, item_idxs: list[int], lang: str = DEFAULT_LANGUAGE
    ) -> list[dict[str, Any]]:
        """Decorate an already-ranked list of item_idx values, order preserved."""
        serialized: list[dict[str, Any]] = []
        for item_idx in item_idxs:
            try:
                serialized.append(self.serialize_item(item_idx, lang))
            except KeyError:
                continue
        return serialized

    def get_popular_items(
        self, limit: int = 10, lang: str = DEFAULT_LANGUAGE
    ) -> list[dict[str, Any]]:
        # Candidate order comes from the model layer, not from the catalog.
        return self.serialize_items(item_embeddings.sorted_item_idxs[:limit], lang)


catalog = CourseCatalog()
