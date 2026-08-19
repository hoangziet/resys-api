from __future__ import annotations

import importlib.util
import logging
import os

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator

from api.deps import Lang, get_lang
from core import database, search
from core.catalog_seed import DIFFICULTY_LABELS
from core.config import settings
from core.security import require_admin
from models.catalog import catalog
from models.embeddings import item_embeddings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])

_EMBEDDING_JOB_COMMAND = "python -m scripts.generate_embeddings"


def _multilabel(value: str | list[str] | None) -> str | None:
    """Normalize a multilabel field to the stored comma-separated form."""
    if value is None:
        return None
    parts = value if isinstance(value, list) else str(value).split(",")
    cleaned = [part.strip() for part in parts if str(part).strip()]
    return ", ".join(cleaned) or None


class CourseCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    description: str | None = None
    difficulty: str | None = Field(
        default=None, description="beginner | intermediate | advanced"
    )
    theme: str | list[str] | None = None
    software: str | list[str] | None = None
    job_type: str | list[str] | None = None
    type: str | None = Field(default=None, description="tutorial | webcast | use_case")
    duration: float | None = Field(default=None, ge=0)
    thumbnail_path: str | None = None

    @field_validator("difficulty")
    @classmethod
    def _known_difficulty(cls, value: str | None) -> str | None:
        if value is None or value == "":
            return None
        key = value.strip().lower()
        if key not in DIFFICULTY_LABELS:
            raise ValueError(
                f"difficulty must be one of {sorted(DIFFICULTY_LABELS)}, got {value!r}"
            )
        return key

    def to_columns(self) -> dict:
        """Map the request onto course table columns."""
        return {
            "title": self.title.strip(),
            "description": self.description,
            # Stored as "<level> - <Label>" so facet_slug() derives the slug back.
            "difficulty": DIFFICULTY_LABELS[self.difficulty] if self.difficulty else None,
            "theme": _multilabel(self.theme),
            "software": _multilabel(self.software),
            "job": _multilabel(self.job_type),
            "type": self.type.strip() if self.type else None,
            "duration": self.duration,
            "thumbnail_path": self.thumbnail_path,
            "text": f"{self.title.strip()}\n{self.description or ''}".strip(),
        }


class CourseUpdate(CourseCreate):
    title: str | None = Field(default=None, min_length=1, max_length=500)

    def to_columns(self) -> dict:
        """Only the fields the caller actually set, so PUT is a partial update."""
        provided = self.model_dump(exclude_unset=True)
        columns: dict = {}
        if "title" in provided and self.title:
            columns["title"] = self.title.strip()
        if "description" in provided:
            columns["description"] = self.description
        if "difficulty" in provided:
            columns["difficulty"] = (
                DIFFICULTY_LABELS[self.difficulty] if self.difficulty else None
            )
        for field, column in (
            ("theme", "theme"),
            ("software", "software"),
            ("job_type", "job"),
        ):
            if field in provided:
                columns[column] = _multilabel(getattr(self, field))
        if "type" in provided:
            columns["type"] = self.type.strip() if self.type else None
        if "duration" in provided:
            columns["duration"] = self.duration
        if "thumbnail_path" in provided:
            columns["thumbnail_path"] = self.thumbnail_path
        return columns


# --------------------------------------------------------------------------
# Course management
# --------------------------------------------------------------------------


@router.get("/courses")
def admin_list_courses(
    q: str | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(search.DEFAULT_LIMIT, ge=1, le=search.MAX_LIMIT),
    lang: Lang = Depends(get_lang),
    user=Depends(require_admin),
) -> dict:
    """Paginated course list for the admin table.

    Reuses the same search engine as the public endpoint so there is only one
    query path, then annotates each row with its embedding status.
    """
    rows, total = search.search_courses(lang=lang, q=q, page=page, limit=limit)
    courses = [catalog.serialize_query_row(row) for row in rows]

    statuses = database.get_embedding_statuses([c["item_idx"] for c in courses])
    ceiling = _model_ceiling()
    for course in courses:
        idx = course["item_idx"]
        course["embedding_status"] = statuses.get(idx, "ready")
        course["in_model_vocabulary"] = 0 < idx <= ceiling

    return {
        "courses": courses,
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total,
            "total_pages": search.total_pages(total, limit),
        },
        "lang": lang,
    }


@router.post("/courses", status_code=201)
def admin_create_course(body: CourseCreate, user=Depends(require_admin)) -> dict:
    item_idx = database.create_course(body.to_columns())
    if item_idx is None:
        raise HTTPException(status_code=500, detail="Failed to create course")

    # Refresh the in-memory display cache so the course is immediately visible.
    catalog.load()

    return {
        "status": "created",
        "item_idx": item_idx,
        "course": database.get_course_admin_row(item_idx),
        "recommendation_availability": _availability(item_idx),
    }


@router.put("/courses/{item_idx}")
def admin_update_course(
    item_idx: int, body: CourseUpdate, user=Depends(require_admin)
) -> dict:
    columns = body.to_columns()
    if not columns:
        raise HTTPException(status_code=422, detail="No updatable fields provided")

    if not database.course_exists(item_idx):
        raise HTTPException(
            status_code=404, detail=f"Course with item_idx {item_idx} not found"
        )

    if not database.update_course(item_idx, columns):
        raise HTTPException(status_code=500, detail="Failed to update course")

    catalog.load()
    return {
        "status": "updated",
        "item_idx": item_idx,
        "course": database.get_course_admin_row(item_idx),
    }


@router.delete("/courses/{item_idx}")
def admin_delete_course(
    item_idx: int,
    force: bool = Query(
        False,
        description="Delete even when the course is inside the model vocabulary",
    ),
    user=Depends(require_admin),
) -> dict:
    if not database.course_exists(item_idx):
        raise HTTPException(
            status_code=404, detail=f"Course with item_idx {item_idx} not found"
        )

    ceiling = _model_ceiling()
    if not force and 0 < item_idx <= ceiling:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Course {item_idx} is inside the BERT4Rec vocabulary (n_items="
                f"{ceiling}). The checkpoint will keep predicting it and the "
                "embedding tensor still holds its row, so deleting it degrades "
                "recommendation quality until the model is retrained. Pass "
                "force=true to delete anyway."
            ),
        )

    if not database.delete_course(item_idx):
        raise HTTPException(status_code=500, detail="Failed to delete course")

    catalog.load()
    return {"status": "deleted", "item_idx": item_idx, "forced": force}


# --------------------------------------------------------------------------
# Recommendation pipeline status
# --------------------------------------------------------------------------


def _model_ceiling() -> int:
    from api.recommendations import model_item_ceiling

    return model_item_ceiling()


def _availability(item_idx: int) -> dict:
    """Which recommenders a given course currently participates in."""
    ceiling = _model_ceiling()
    row = database.get_course_admin_row(item_idx) or {}
    has_embedding = item_embeddings.has_embedding(item_idx)
    return {
        "search_and_filter": True,
        "trending": True,
        "text_similarity": has_embedding,
        "bert4rec": 0 < item_idx <= ceiling,
        "embedding_status": row.get("embedding_status") or "ready",
        "next_step": (
            None
            if has_embedding
            else f"Run the embedding job: {_EMBEDDING_JOB_COMMAND}"
        ),
    }


@router.get("/pipeline-status")
def pipeline_status(user=Depends(require_admin)) -> dict:
    """What a newly created course is and is not yet part of.

    The three item universes drift apart as soon as courses are added:
    the catalog grows on insert, the embedding tensor only when the offline job
    runs, and the BERT4Rec vocabulary only on retraining.
    """
    catalog_count = database.count_courses()
    pending = database.get_courses_pending_embedding(limit=500)
    ceiling = _model_ceiling()

    return {
        "catalog": {"courses": catalog_count},
        "text_similarity": {
            "embedding_rows": item_embeddings.max_embedding_idx,
            "pending_courses": len(pending),
            "pending_item_idxs": [row["item_idx"] for row in pending][:50],
            "action_required": bool(pending),
            "command": _EMBEDDING_JOB_COMMAND,
        },
        "bert4rec": {
            "n_items": ceiling,
            "courses_outside_vocabulary": max(catalog_count - ceiling, 0),
            "action_required": catalog_count > ceiling,
            "note": (
                "BERT4Rec hard-sizes its input embedding table and output layer from "
                "the checkpoint, and mask_token == n_items + 1. New courses cannot be "
                "served or consumed until the model is retrained; they are filtered "
                "out of model input in the meantime."
            ),
        },
        "trending": {
            "source": "user_history interaction counts",
            "action_required": False,
            "note": "Any catalog course can trend as soon as it is interacted with.",
        },
    }


@router.post("/sync-catalog")
def sync_catalog(user=Depends(require_admin)) -> dict:
    """Re-seed the catalog from CSV, rebuild facets and reload the cache."""
    from core.catalog_seed import rebuild_course_facets, seed_courses

    conn = database.get_connection()
    try:
        cursor = conn.cursor()
        seeded = seed_courses(cursor)
        # Force a facet rebuild so a manual sync always leaves them consistent.
        facet_rows = rebuild_course_facets(cursor)
        conn.commit()
    except Exception as exc:
        conn.rollback()
        logger.exception("Catalog sync failed")
        raise HTTPException(status_code=500, detail=f"Catalog sync failed: {exc}") from exc
    finally:
        conn.close()

    catalog.load()
    return {
        "status": "ok",
        "action": "sync_catalog",
        "seeded": seeded,
        "facet_rows": facet_rows,
        "courses": database.count_courses(),
    }


@router.post("/rebuild-embeddings")
def rebuild_embeddings(user=Depends(require_admin)) -> dict:
    """Generate embeddings for courses that do not have one yet.

    Requires the optional encoder dependency; without it there is no way to
    produce a CamemBERT vector, so this reports what needs doing rather than
    claiming success.
    """
    pending = database.get_courses_pending_embedding(limit=500)
    if not pending:
        return {
            "status": "ok",
            "action": "rebuild_embeddings",
            "pending_courses": 0,
            "detail": "Every course already has an embedding.",
        }

    if importlib.util.find_spec("sentence_transformers") is None:
        raise HTTPException(
            status_code=501,
            detail=(
                f"{len(pending)} course(s) need an embedding, but the encoder "
                "dependency is not installed in this environment. Run the offline "
                f"job where it is available: {_EMBEDDING_JOB_COMMAND} "
                "(install with: uv sync --extra embeddings)"
            ),
        )

    from scripts.generate_embeddings import generate_pending_embeddings

    try:
        result = generate_pending_embeddings()
    except Exception as exc:
        logger.exception("Embedding generation failed")
        raise HTTPException(
            status_code=500, detail=f"Embedding generation failed: {exc}"
        ) from exc

    return {"status": "ok", "action": "rebuild_embeddings", **result}


# --------------------------------------------------------------------------
# Monitoring
# --------------------------------------------------------------------------


@router.get("/latency-stats")
def latency_stats(
    hours: int = Query(24, ge=1, le=24 * 90, description="Look-back window in hours"),
    user=Depends(require_admin),
) -> dict:
    """Latency percentiles for recommendation endpoints, plus an hourly series."""
    stats = database.get_latency_stats(hours=hours)
    return {
        **stats,
        "timeseries": database.get_latency_timeseries(hours=hours),
        "note": "median == p50 (the same percentile); both are reported by convention.",
    }


@router.get("/model-health")
def model_health(user=Depends(require_admin)) -> dict:
    exists = os.path.exists(settings.model_checkpoint_path)
    if exists:
        try:
            from api.recommendations import get_model

            model = get_model()
            if model is None:
                return {
                    "status": "degraded",
                    "artifact": "bert4rec.pt",
                    "error": "Model not loaded",
                }
            return {
                "status": "healthy",
                "artifact": "bert4rec.pt",
                "vocab_size": model.vocab_size,
                "max_len": model.pos_embedding.num_embeddings,
                "hidden_dim": model.hidden_dim,
                "n_items": model.n_items,
                "embedding_rows": item_embeddings.max_embedding_idx,
            }
        except Exception as exc:
            return {"status": "degraded", "artifact": "bert4rec.pt", "error": str(exc)}
    return {
        "status": "error",
        "message": f"Checkpoint not found at {settings.model_checkpoint_path}",
    }


@router.get("/recommendation-logs")
def recommendation_logs(user=Depends(require_admin)) -> dict:
    logs = database.get_recommendation_logs(limit=100)
    return {"logs": logs}


@router.post("/cleanup-logs")
def cleanup_logs(user=Depends(require_admin)) -> dict:
    deleted = database.cleanup_recommendation_logs(settings.log_retention_days)
    return {"deleted": deleted, "retention_days": settings.log_retention_days}
