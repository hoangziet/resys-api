"""Recommendation model package."""

from .bert4rec import (BERT4Rec, TextItemEncoder, get_model,
                       resolve_artifact_path)

__all__ = ["BERT4Rec", "TextItemEncoder", "get_model", "resolve_artifact_path"]
