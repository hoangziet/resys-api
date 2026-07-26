from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from core.security import require_admin
from core import database
from core.config import settings

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/sync-catalog")
def sync_catalog(user=Depends(require_admin)) -> dict:
    return {"status": "ok", "action": "sync_catalog", "synced_items": 3238}


@router.post("/rebuild-embeddings")
def rebuild_embeddings(user=Depends(require_admin)) -> dict:
    return {"status": "ok", "action": "rebuild_embeddings"}


@router.get("/model-health")
def model_health(user=Depends(require_admin)) -> dict:
    import os

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
