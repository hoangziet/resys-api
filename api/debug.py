from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from core.config import settings
from core.security import TokenData, require_admin

router = APIRouter(prefix="/debug", tags=["debug"])


@router.get("/infer")
def debug_infer(token_data: TokenData = Depends(require_admin)):
    """Load the promoted artifact and run a sample prediction for CLI testing.

    Admin-only in development. Disabled entirely in production.
    """
    if settings.environment == "production":
        raise HTTPException(status_code=404, detail="Not found")
    try:
        from inference import load_model, predict

        model, n_items, max_len = load_model(settings.model_checkpoint_path)
        history = [1, 2, 3]
        results = predict(model, history, max_len=max_len, top_k=10)
        return {"history": history, "results": results}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Model load failed: {exc}")
