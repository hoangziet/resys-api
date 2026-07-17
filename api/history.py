from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from core.security import verify_token

router = APIRouter(prefix="/history", tags=["history"])


@router.get("/")
def get_history(token_data=Depends(verify_token)) -> dict:
    # Placeholder: return the authenticated user's learning history.
    return {"user": token_data.username, "history": []}


@router.post("/")
def add_history_item(item_id: int, token_data=Depends(verify_token)) -> dict:
    # Placeholder: add an item to the user's history.
    return {"user": token_data.username, "item_id": item_id, "status": "added"}


@router.delete("/{item_id}")
def remove_history_item(item_id: int, token_data=Depends(verify_token)) -> dict:
    # Placeholder: remove an item from the user's history.
    return {"user": token_data.username, "item_id": item_id, "status": "removed"}
