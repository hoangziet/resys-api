from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from api.deps import Lang, get_lang
from core import search
from core.catalog_seed import DIFFICULTY_SLUGS
from core.security import verify_token
from models.catalog import catalog

router = APIRouter(prefix="/courses", tags=["courses"])

# Public query-parameter name -> course_facets.kind. "job" is exposed as "job_type".
FACET_PARAMS: dict[str, str] = {
    "difficulty": "difficulty",
    "theme": "theme",
    "software": "software",
    "job_type": "job",
    "type": "type",
}

# Difficulty is an ordered scale, so it is presented in level order rather than by
# popularity like the other facets.
_DIFFICULTY_ORDER = {slug: int(level) for level, slug in DIFFICULTY_SLUGS.items()}


@router.get("/")
def list_courses(
    q: str | None = Query(
        None, description="Free-text query; tokens are matched against title, "
        "description, theme, software and job"
    ),
    difficulty: list[str] = Query(default_factory=list),
    theme: list[str] = Query(default_factory=list),
    software: list[str] = Query(default_factory=list),
    job_type: list[str] = Query(default_factory=list),
    # Shadows the `type` builtin deliberately: the public query name mirrors the
    # course column. Not used as a callable in this function.
    type: list[str] = Query(
        default_factory=list, description="Course format: tutorial, webcast, use_case"
    ),
    page: int = Query(1, ge=1, description="1-based page number"),
    limit: int = Query(
        search.DEFAULT_LIMIT, ge=1, le=search.MAX_LIMIT, description="Courses per page"
    ),
    lang: Lang = Depends(get_lang),
    token_data=Depends(verify_token),
) -> dict:
    """Search + filter + paginated course list.

    Search tokens AND together and each may match any of title, description,
    theme, software or job. Filters combine: values within one filter are OR-ed,
    different filters are AND-ed, and an omitted filter does not restrict
    anything. Searching, filtering and pagination all happen in SQL - only the
    requested page leaves the database.
    """
    facets = {
        "difficulty": difficulty,
        "theme": theme,
        "software": software,
        "job": job_type,
        "type": type,
    }

    rows, total = search.search_courses(
        lang=lang, q=q, facets=facets, page=page, limit=limit
    )

    return {
        "courses": [catalog.serialize_query_row(row) for row in rows],
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total,
            "total_pages": search.total_pages(total, limit),
        },
        "lang": lang,
    }


# Declared before /{course_id}: otherwise FastAPI tries to parse "filters" as an int
# and this endpoint 422s.
@router.get("/filters")
def list_filters(
    lang: Lang = Depends(get_lang),
    token_data=Depends(verify_token),
) -> dict:
    """Available filter values for a language, with course counts.

    Values are slugs of the labels in the requested language, so a client should
    refetch this when the display language changes and drop selections that no
    longer appear. Difficulty slugs are language-independent.
    """
    options = search.get_facet_options(lang)

    grouped: dict[str, list[dict]] = {param: [] for param in FACET_PARAMS}
    kind_to_param = {kind: param for param, kind in FACET_PARAMS.items()}
    for option in options:
        param = kind_to_param.get(option["kind"])
        if param is None:
            continue
        grouped[param].append(
            {
                "value": option["slug"],
                "label": option["label"],
                "count": option["count"],
            }
        )

    for _, values in grouped.items():
        values.sort(key=lambda v: v["label"].lower())
    return {"lang": lang, "filters": grouped}


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
