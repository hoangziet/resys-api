from __future__ import annotations

from fastapi import APIRouter, Depends

from core.security import require_admin

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/sync-catalog")
def sync_catalog(user=Depends(require_admin)) -> dict:
    # Placeholder: sync course catalog from processed metadata into the database.
    return {"status": "ok", "action": "sync_catalog"}


@router.post("/rebuild-embeddings")
def rebuild_embeddings(user=Depends(require_admin)) -> dict:
    # Placeholder: trigger course embedding rebuild.
    return {"status": "ok", "action": "rebuild_embeddings"}


@router.get("/model-health")
def model_health(user=Depends(require_admin)) -> dict:
    # Placeholder: inspect promoted BERT4Rec artifact health.
    return {"status": "healthy", "artifact": "current"}


@router.get("/recommendation-logs")
def recommendation_logs(user=Depends(require_admin)) -> dict:
    # Placeholder: inspect recommendation request/result logs.
    return {"logs": []}
