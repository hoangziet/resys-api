from __future__ import annotations

from fastapi import APIRouter, HTTPException

from core.config import settings

router = APIRouter(prefix="/debug", tags=["debug"])


@router.get("/infer")
def debug_infer():
    """Load the promoted artifact and run a sample prediction for CLI testing.

    Returns a compact list of (item_idx, score) for history [1,2,3].
    """
    try:
        # Import inference helpers lazily to avoid heavy imports at app startup
        from inference import load_model, predict

        model, n_items, max_len = load_model(settings.model_checkpoint_path)
        history = [1, 2, 3]
        results = predict(model, history, max_len=max_len, top_k=10)
        return {"history": history, "results": results}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Model load failed: {exc}")
