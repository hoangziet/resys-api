from __future__ import annotations

import logging
import math
import threading
import time
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel, Field

from core.config import settings
from core.rate_limit import limiter
from inference import load_model, predict
from models.embeddings import item_embeddings
from core.security import verify_token
from core import database

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


@router.post("/popular")
@limiter.limit("5/second")
def popular_courses(
    request: Request, body: RecommenderRequest, token_data=Depends(verify_token)
) -> dict:
    start_time = time.perf_counter()
    items = item_embeddings.get_popular_items(limit=body.limit)
    latency_ms = (time.perf_counter() - start_time) * 1000

    database.log_recommendation(
        username=token_data.username,
        strategy="popularity_nb_views",
        latency_ms=latency_ms,
        history=[],
        results=[item["item_idx"] for item in items],
    )

    return {
        "source": "popular",
        "items": items,
        "limit": body.limit,
        "latency_ms": latency_ms,
    }


@router.post("/for-you")
@limiter.limit("5/second")
def for_you(
    request: Request, body: RecommenderRequest, token_data=Depends(verify_token)
) -> dict:
    start_time = time.perf_counter()

    history = body.history
    if not history:
        history = database.get_user_history(token_data.username)

    if not history:
        return {
            "source": "bert4rec",
            "items": [],
            "limit": body.limit,
            "latency_ms": 0.0,
        }

    try:
        model = get_model()
        if model is None:
            raise RuntimeError("Model not loaded")
        top_items = predict(
            model,
            history,
            max_len=model.pos_embedding.num_embeddings,
            top_k=body.limit,
        )

        logits = [score for _, score in top_items]
        max_logit = max(logits) if logits else 0.0
        exp_logits = [math.exp(l - max_logit) for l in logits]
        sum_exp = sum(exp_logits)
        probs = (
            [e / sum_exp for e in exp_logits] if sum_exp > 0 else [0.0] * len(logits)
        )

        items = [
            item_embeddings.serialize_item(item_idx) | {"score": prob}
            for (item_idx, _), prob in zip(top_items, probs)
        ]
        strategy = "bert4rec_personalized"
    except Exception:
        items = item_embeddings.get_popular_items(limit=body.limit)
        strategy = "popular_fallback_error"

    latency_ms = (time.perf_counter() - start_time) * 1000
    database.log_recommendation(
        username=token_data.username,
        strategy=strategy,
        latency_ms=latency_ms,
        history=history,
        results=[item["item_idx"] for item in items],
    )

    return {
        "source": strategy,
        "items": items,
        "limit": body.limit,
        "latency_ms": latency_ms,
    }


@router.post("/you-may-also-like")
@limiter.limit("5/second")
def you_may_also_like(
    request: Request, body: RecommenderRequest, token_data=Depends(verify_token)
) -> dict:
    start_time = time.perf_counter()

    history = body.history
    if not history:
        history = database.get_user_history(token_data.username)

    if not history:
        return {
            "source": "vector_similarity",
            "items": [],
            "limit": body.limit,
            "latency_ms": 0.0,
        }

    anchor_idx = history[-1]
    try:
        recommendations = item_embeddings.similar_items(anchor_idx, top_k=body.limit)
        items = [
            item_embeddings.serialize_item(item_idx) | {"score": score}
            for item_idx, score in recommendations
        ]
        strategy = "vector_similarity"
    except Exception:
        items = item_embeddings.get_popular_items(limit=body.limit)
        strategy = "popular_fallback_error"

    latency_ms = (time.perf_counter() - start_time) * 1000
    database.log_recommendation(
        username=token_data.username,
        strategy=strategy,
        latency_ms=latency_ms,
        history=history,
        results=[item["item_idx"] for item in items],
    )

    return {
        "source": strategy,
        "anchor_item_idx": anchor_idx,
        "items": items,
        "limit": body.limit,
        "latency_ms": latency_ms,
    }


@router.post("/similar/{course_id}")
@limiter.limit("5/second")
def similar_courses(
    request: Request,
    course_id: int,
    body: SimilarityRequest,
    token_data=Depends(verify_token),
) -> dict:
    start_time = time.perf_counter()
    try:
        recommendations = item_embeddings.similar_items(course_id, top_k=body.limit)
        items = [
            item_embeddings.serialize_item(item_idx) | {"score": score}
            for item_idx, score in recommendations
        ]
        strategy = "vector_similarity"
    except Exception:
        items = item_embeddings.get_popular_items(limit=body.limit)
        strategy = "popular_fallback_error"

    latency_ms = (time.perf_counter() - start_time) * 1000
    database.log_recommendation(
        username=token_data.username,
        strategy=strategy,
        latency_ms=latency_ms,
        history=[course_id],
        results=[item["item_idx"] for item in items],
    )

    return {
        "source": strategy,
        "course_id": course_id,
        "items": items,
        "limit": body.limit,
        "latency_ms": latency_ms,
    }
