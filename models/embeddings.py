from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

import torch
import torch.nn.functional as F
from torch import Tensor

TEXT_EMBEDDINGS_PATH = Path("models/sentence-camembert-base.pt")
ALT_TEXT_EMBEDDINGS_PATH = Path("models/sentence-camembert-base.pt")
METADATA_CSV_PATH = Path("data/processed/item_features/item_metadata.csv")


class ItemEmbeddings:
    """Model-side view of the catalog: French text embeddings + the valid item_idx set.

    Deliberately French-only and free of any database dependency - this is what
    BERT4Rec and the vector-similarity path are built on. Localized text for API
    responses lives in models/catalog.py, which reads courses/courses_en from
    SQLite and never feeds anything back into this layer. self.metadata is kept as
    the catalog's fallback when a course row is missing from the database.
    """

    def __init__(
        self,
        embeddings_path: Path = TEXT_EMBEDDINGS_PATH,
        metadata_path: Path = METADATA_CSV_PATH,
    ):
        self.embeddings = self._load_embeddings(embeddings_path)
        self.metadata = self._load_metadata(metadata_path)
        self.item_idx_set = set(self.metadata.keys())
        self.sorted_item_idxs = sorted(self.item_idx_set)
        self.n_items = len(self.sorted_item_idxs)
        self.normalized_embeddings = F.normalize(self.embeddings, p=2, dim=1)

    def _load_embeddings(self, path: Path) -> Tensor:
        if path.exists():
            source_path = path
        elif ALT_TEXT_EMBEDDINGS_PATH.exists():
            source_path = ALT_TEXT_EMBEDDINGS_PATH
        else:
            raise FileNotFoundError(
                f"Text embedding checkpoint not found: {path} or {ALT_TEXT_EMBEDDINGS_PATH}"
            )
        embeddings = torch.load(source_path, map_location="cpu", weights_only=True)
        if embeddings.dim() != 2:
            raise ValueError(
                f"Expected 2D tensor for embeddings, got {embeddings.dim()}D"
            )
        return embeddings

    def _load_metadata(self, path: Path) -> dict[int, dict[str, Any]]:
        if not path.exists():
            raise FileNotFoundError(f"Item metadata file not found: {path}")
        metadata: dict[int, dict[str, Any]] = {}
        with path.open("r", newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                item_idx = int(row["item_idx"])
                metadata[item_idx] = {
                    "item_idx": item_idx,
                    "item_id": row.get("item_id"),
                    "title": row.get("title", ""),
                    "description": row.get("description", ""),
                    "language": row.get("language", ""),
                    "difficulty": row.get("difficulty", ""),
                    "theme": row.get("theme", ""),
                    "software": row.get("software", ""),
                    "job": row.get("job", ""),
                    "type": row.get("type", ""),
                    "duration": self._parse_float(row.get("duration")),
                }
        return metadata

    @staticmethod
    def _parse_float(value: str | None) -> float | None:
        if value is None or value == "":
            return None
        try:
            return float(value)
        except ValueError:
            return None

    @property
    def max_embedding_idx(self) -> int:
        """Highest item_idx that has a row in the embedding tensor.

        Row 0 is the padding row, so valid item rows are 1..max_embedding_idx.
        Courses created after the tensor was built fall outside this range and
        cannot participate in text similarity until the offline embedding job runs.
        """
        return self.embeddings.size(0) - 1

    def has_embedding(self, item_idx: int) -> bool:
        """Whether this course can be used for vector similarity."""
        return 1 <= item_idx <= self.max_embedding_idx

    def similar_items(self, item_idx: int, top_k: int = 10) -> list[tuple[int, float]]:
        if item_idx not in self.item_idx_set:
            raise KeyError(f"Unknown item_idx: {item_idx}")
        if item_idx >= self.embeddings.size(0):
            raise IndexError(
                f"item_idx {item_idx} is out of range for embeddings shape {self.embeddings.shape}"
            )

        query_vec = self.normalized_embeddings[item_idx].unsqueeze(0)
        scores = torch.matmul(query_vec, self.normalized_embeddings.T).squeeze(0)
        scores[item_idx] = float("-inf")
        top_k = min(top_k, scores.numel() - 1)
        values, indices = torch.topk(scores, top_k)
        return [
            (int(idx.item()), float(value.item()))
            for idx, value in zip(indices, values, strict=True)
        ]


item_embeddings = ItemEmbeddings()
