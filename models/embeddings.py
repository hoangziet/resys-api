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
THUMBNAIL_URL = "/assets/thumbnail.png"
VIDEO_URL = "/assets/video.mp4"


class ItemEmbeddings:
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

    def serialize_item(self, item_idx: int) -> dict[str, Any]:
        if item_idx not in self.metadata:
            raise KeyError(f"Unknown item_idx: {item_idx}")
        item = dict(self.metadata[item_idx])
        item["thumbnail_url"] = THUMBNAIL_URL
        item["video_url"] = VIDEO_URL
        return item

    def get_popular_items(self, limit: int = 10) -> list[dict[str, Any]]:
        item_idxs = self.sorted_item_idxs[:limit]
        return [self.serialize_item(item_idx) for item_idx in item_idxs]

    def search_items(
        self, query: str | None = None, limit: int = 20
    ) -> list[dict[str, Any]]:
        if not query:
            return self.get_popular_items(limit=limit)
        query_text = query.strip().lower()
        results: list[tuple[int, int]] = []
        for item_idx in self.sorted_item_idxs:
            item = self.metadata[item_idx]
            title = item.get("title", "").lower()
            description = item.get("description", "").lower()
            score = 0
            if query_text in title:
                score += 10
            if query_text in description:
                score += 2
            if score:
                results.append((item_idx, score))
        results.sort(key=lambda row: (-row[1], row[0]))
        return [self.serialize_item(item_idx) for item_idx, _ in results[:limit]]

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
