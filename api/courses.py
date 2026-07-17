from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from core.security import verify_token

router = APIRouter(prefix="/courses", tags=["courses"])


@router.get("/")
def list_courses(q: str | None = Query(None, description="Search query"), token_data=Depends(verify_token)) -> dict:
    # Placeholder: implement catalog search and pagination.
    return {"data": [], "total": 0, "query": q}


@router.get("/{course_id}")
def get_course(course_id: int, token_data=Depends(verify_token)) -> dict:
    # Placeholder: return course detail metadata.
    return {"course_id": course_id, "title": None, "description": None, "is_model_known": False}
