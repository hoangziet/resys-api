from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from api.deps import Lang, get_lang
from core import database
from core.security import verify_token
from models.catalog import catalog
from models.embeddings import item_embeddings

router = APIRouter(prefix="/history", tags=["history"])


@router.get("/")
def get_history(
    lang: Lang = Depends(get_lang), token_data=Depends(verify_token)
) -> dict:
    history_idxs = database.get_user_history(token_data.username)
    serialized_history = catalog.serialize_items(history_idxs, lang=lang)
    return {
        "user": token_data.username,
        "history": serialized_history,
        "lang": lang,
    }


@router.post("/")
def add_history_item(item_idx: int, token_data=Depends(verify_token)) -> dict:
    if item_idx not in item_embeddings.item_idx_set:
        raise HTTPException(
            status_code=404, detail=f"Course with item_idx {item_idx} not found"
        )

    success = database.add_history_item(token_data.username, item_idx)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to add item to history")
    return {"user": token_data.username, "item_idx": item_idx, "status": "added"}


@router.delete("/{item_idx}")
def remove_history_item(item_idx: int, token_data=Depends(verify_token)) -> dict:
    success = database.remove_history_item(token_data.username, item_idx)
    if not success:
        raise HTTPException(
            status_code=500, detail="Failed to remove item from history"
        )
    return {"user": token_data.username, "item_idx": item_idx, "status": "removed"}


@router.delete("/")
def clear_history(token_data=Depends(verify_token)) -> dict:
    success = database.clear_user_history(token_data.username)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to clear history")
    return {"user": token_data.username, "status": "cleared"}
