from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from core.security import verify_token

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


@router.get("/popular")
def popular_courses(token_data=Depends(verify_token), limit: int = Query(10, ge=1, le=50)) -> dict:
    # Placeholder: return popularity-based top courses.
    return {"source": "popular_fallback", "items": [], "limit": limit}


@router.get("/for-you")
def for_you(token_data=Depends(verify_token), limit: int = Query(10, ge=1, le=50)) -> dict:
    # Placeholder: return personalized recommendations.
    return {"source": "bert4rec", "items": [], "limit": limit}


@router.get("/you-may-also-like")
def you_may_also_like(token_data=Depends(verify_token), limit: int = Query(10, ge=1, le=50)) -> dict:
    # Placeholder: return vector similarity or fallback results.
    return {"source": "vector_similarity", "items": [], "limit": limit}


@router.get("/similar/{course_id}")
def similar_courses(course_id: int, token_data=Depends(verify_token), limit: int = Query(10, ge=1, le=50)) -> dict:
    # Placeholder: return course-detail similar course recommendations.
    return {"source": "vector_similarity", "course_id": course_id, "items": [], "limit": limit}
