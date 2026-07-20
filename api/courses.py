from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from core.security import verify_token
from models.embeddings import item_embeddings

router = APIRouter(prefix="/courses", tags=["courses"])


@router.get("/")
def list_courses(q: str | None = Query(None, description="Search query"), token_data=Depends(verify_token)) -> dict:
    results = item_embeddings.search_items(q, limit=100)
    return {"data": results, "total": len(results), "query": q}


@router.get("/{course_id}")
def get_course(course_id: int, token_data=Depends(verify_token)) -> dict:
    try:
        return item_embeddings.serialize_item(course_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Course with item_idx {course_id} not found")

