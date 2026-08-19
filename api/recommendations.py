from __future__ import annotations

import logging
import math
import threading
import time

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from api.deps import Lang, get_lang
from core import database, monitoring
from core.config import settings
from core.rate_limit import limiter
from core.security import verify_token
from inference import load_model, predict
from models.catalog import catalog
from models.embeddings import item_embeddings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


class RecommenderRequest(BaseModel):
    history: list[int] = Field(default_factory=list)
    limit: int = Field(default=10, ge=1, le=50)


class SimilarityRequest(BaseModel):
    limit: int = Field(default=10, ge=1, le=50)


_model = None
_model_lock = threading.Lock()


def get_model():
    return _model


def load_recommendation_model():
    global _model
    with _model_lock:
        if _model is None:
            model, _, _ = load_model(settings.model_checkpoint_path)
            _model = model
            logger.info("Recommendation model loaded at startup")


def model_item_ceiling() -> int:
    """Highest item_idx the BERT4Rec checkpoint knows.

    The checkpoint hard-sizes both the input embedding table and the output layer
    (models/bert4rec.py: item_embedding is nn.Embedding(n_items+2) and forward()
    ties logits to item_embedding.weight[1:n_items+1]), so this cannot grow
    without retraining.
    """
    model = get_model()
    return int(model.n_items) if model is not None else 0


def model_history(history: list[int]) -> list[int]:
    """Restrict a user's history to items BERT4Rec can actually consume.

    Critical: ``mask_token == n_items + 1``, so the first item_idx past the
    training catalog is numerically identical to the mask token. Passing a
    newly created course straight through would be silently read as [MASK] and
    corrupt the sequence. user_history is application data and may contain any
    catalog course, so it must be projected onto the model vocabulary here.
    """
    ceiling = model_item_ceiling()
    if ceiling <= 0:
        return []
    return [item_idx for item_idx in history if 1 <= item_idx <= ceiling]


def _similarity_anchor(history: list[int]) -> int | None:
    """Most recent history item that has an embedding row."""
    for item_idx in reversed(history):
        if item_embeddings.has_embedding(item_idx):
            return item_idx
    return None


def _trending(limit: int, lang: str) -> list[dict]:
    return catalog.get_popular_items(limit=limit, lang=lang)


@router.post("/popular")
@limiter.limit("5/second")
def popular_courses(
    request: Request,
    body: RecommenderRequest,
    lang: Lang = Depends(get_lang),
    token_data=Depends(verify_token),
) -> dict:
    start_time = time.perf_counter()
    items = _trending(body.limit, lang)
    latency_ms = (time.perf_counter() - start_time) * 1000

    monitoring.record(
        request,
        strategy="popularity_nb_views",
        history=[],
        results=[item["item_idx"] for item in items],
        username=token_data.username,
    )

    return {
        "source": "popular",
        "items": items,
        "limit": body.limit,
        "lang": lang,
        "latency_ms": latency_ms,
    }


@router.post("/for-you")
@limiter.limit("5/second")
def for_you(
    request: Request,
    body: RecommenderRequest,
    lang: Lang = Depends(get_lang),
    token_data=Depends(verify_token),
) -> dict:
    start_time = time.perf_counter()

    history = body.history
    if not history:
        history = database.get_user_history(token_data.username)

    # Only items inside the model vocabulary may reach predict().
    usable_history = model_history(history)

    if not usable_history:
        # Either no history at all, or the user has only interacted with courses
        # added after the checkpoint was trained.
        items = _trending(body.limit, lang) if history else []
        strategy = "popular_fallback_cold_start" if history else "bert4rec"
        model = get_model()
        if model is not None:
            items = [i for i in items if i["item_idx"] <= model.n_items]

        latency_ms = (time.perf_counter() - start_time) * 1000
        monitoring.record(
            request,
            strategy=strategy,
            history=history,
            results=[item["item_idx"] for item in items],
            username=token_data.username,
        )
        return {
            "source": strategy,
            "items": items,
            "limit": body.limit,
            "lang": lang,
            "latency_ms": latency_ms,
        }

    try:
        model = get_model()
        if model is None:
            raise RuntimeError("Model not loaded")
        top_items = predict(
            model,
            usable_history,
            max_len=model.pos_embedding.num_embeddings,
            top_k=body.limit,
        )

        logits = [score for _, score in top_items]
        max_logit = max(logits) if logits else 0.0
        exp_logits = [math.exp(logit - max_logit) for logit in logits]
        sum_exp = sum(exp_logits)
        probs = (
            [e / sum_exp for e in exp_logits] if sum_exp > 0 else [0.0] * len(logits)
        )

        items = [
            catalog.serialize_item(item_idx, lang=lang) | {"score": prob}
            for (item_idx, _), prob in zip(top_items, probs, strict=True)
        ]
        strategy = "bert4rec_personalized"
    except Exception:
        logger.exception("BERT4Rec inference failed, falling back to popular")
        items = _trending(body.limit, lang)
        strategy = "popular_fallback_error"

    model = get_model()
    if model is not None:
        items = [i for i in items if i["item_idx"] <= model.n_items]

    latency_ms = (time.perf_counter() - start_time) * 1000
    monitoring.record(
        request,
        strategy=strategy,
        history=usable_history,
        results=[item["item_idx"] for item in items],
        username=token_data.username,
    )

    return {
        "source": strategy,
        "items": items,
        "limit": body.limit,
        "lang": lang,
        "latency_ms": latency_ms,
    }


@router.post("/you-may-also-like")
@limiter.limit("5/second")
def you_may_also_like(
    request: Request,
    body: RecommenderRequest,
    lang: Lang = Depends(get_lang),
    token_data=Depends(verify_token),
) -> dict:
    start_time = time.perf_counter()

    history = body.history
    if not history:
        history = database.get_user_history(token_data.username)

    if not history:
        monitoring.record(
            request, strategy="vector_similarity", username=token_data.username
        )
        return {
            "source": "vector_similarity",
            "items": [],
            "limit": body.limit,
            "lang": lang,
            "latency_ms": 0.0,
        }

    # Anchor on the newest item that actually has an embedding, rather than
    # history[-1], which may be a course still awaiting its vector.
    anchor_idx = _similarity_anchor(history)

    if anchor_idx is None:
        items = _trending(body.limit, lang)
        strategy = "popular_fallback_no_embedding"
    else:
        try:
            recommendations = item_embeddings.similar_items(anchor_idx, top_k=body.limit)
            items = [
                catalog.serialize_item(item_idx, lang=lang) | {"score": score}
                for item_idx, score in recommendations
            ]
            strategy = "vector_similarity"
        except Exception:
            logger.exception(
                "Vector similarity failed for anchor=%d, falling back to popular",
                anchor_idx,
            )
            items = _trending(body.limit, lang)
            strategy = "popular_fallback_error"

    latency_ms = (time.perf_counter() - start_time) * 1000
    monitoring.record(
        request,
        strategy=strategy,
        history=history,
        results=[item["item_idx"] for item in items],
        username=token_data.username,
    )

    return {
        "source": strategy,
        "anchor_item_idx": anchor_idx,
        "items": items,
        "limit": body.limit,
        "lang": lang,
        "latency_ms": latency_ms,
    }


@router.post("/similar/{course_id}")
@limiter.limit("5/second")
def similar_courses(
    request: Request,
    course_id: int,
    body: SimilarityRequest,
    lang: Lang = Depends(get_lang),
    token_data=Depends(verify_token),
) -> dict:
    start_time = time.perf_counter()

    # Distinguish "no such course" from "course exists but has no embedding yet",
    # which is the normal state for a freshly created course.
    if not item_embeddings.has_embedding(course_id):
        if database.course_exists(course_id):
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Course {course_id} has no text embedding yet, so it cannot be "
                    "used for similarity search. Run the embedding job "
                    "(POST /admin/rebuild-embeddings) to make it available."
                ),
            )
        raise HTTPException(
            status_code=404, detail=f"Course with item_idx {course_id} not found"
        )

    try:
        recommendations = item_embeddings.similar_items(course_id, top_k=body.limit)
        items = [
            catalog.serialize_item(item_idx, lang=lang) | {"score": score}
            for item_idx, score in recommendations
        ]
        strategy = "vector_similarity"
    except Exception:
        logger.exception(
            "Vector similarity failed for course=%d, falling back to popular", course_id
        )
        items = _trending(body.limit, lang)
        strategy = "popular_fallback_error"

    latency_ms = (time.perf_counter() - start_time) * 1000
    monitoring.record(
        request,
        strategy=strategy,
        history=[course_id],
        results=[item["item_idx"] for item in items],
        username=token_data.username,
    )

    return {
        "source": strategy,
        "course_id": course_id,
        "items": items,
        "limit": body.limit,
        "lang": lang,
        "latency_ms": latency_ms,
    }
