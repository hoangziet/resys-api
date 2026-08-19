from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from api.deps import Lang, get_lang
from core.security import verify_token
from models.catalog import catalog

router = APIRouter(prefix="/courses", tags=["courses"])


@router.get("/")
def list_courses(
    q: str | None = Query(None, description="Search query"),
    lang: Lang = Depends(get_lang),
    token_data=Depends(verify_token),
) -> dict:
    results = catalog.search_items(q, limit=100, lang=lang)
    return {"data": results, "total": len(results), "query": q, "lang": lang}


@router.get("/{course_id}")
def get_course(
    course_id: int,
    lang: Lang = Depends(get_lang),
    token_data=Depends(verify_token),
) -> dict:
    try:
        return catalog.serialize_item(course_id, lang=lang)
    except KeyError:
        raise HTTPException(
            status_code=404, detail=f"Course with item_idx {course_id} not found"
        ) from None
