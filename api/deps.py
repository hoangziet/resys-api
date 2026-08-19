from __future__ import annotations

from typing import Literal

from fastapi import Query

Lang = Literal["en", "fr"]


def get_lang(
    lang: Lang = Query(
        "en",
        description=(
            "Display language for course text. Affects returned titles/descriptions "
            "only - item selection and ranking always use the French catalog the "
            "recommender was trained on."
        ),
    ),
) -> Lang:
    return lang
