"""
inference.py
============
Lightweight inference utilities for BERT4Rec.

Usage::

    from inference import load_model, predict, recommend

    model, n_items, max_len = load_model("models/checkpoints/bert4rec.pt")
    top_items = predict(model, history=[1, 2, 3], max_len=max_len, top_k=10)
    recs = recommend(model, [1, 2, 3], max_len=max_len, top_k=10)
"""

from __future__ import annotations

import logging
from pathlib import Path

import torch
from torch import Tensor

from core.config import settings

from models.bert4recpy import BERT4Rec, TextItemEncoder

logger = logging.getLogger(__name__)
Device = str | torch.device


def _resolve_device(device: Device | None = None) -> torch.device:
    return torch.device(
        "cuda" if device is None and torch.cuda.is_available() else device or "cpu"
    )


def load_model(
    ckpt_path: str | Path,
    device: Device | None = None,
    text_embeddings_path: str | Path | None = None,
) -> tuple[BERT4Rec, int, int]:
    ckpt_path = Path(ckpt_path)
    if not ckpt_path.exists():
        raise FileNotFoundError(f"Checkpoint not found: {ckpt_path}")

    checkpoint = torch.load(ckpt_path, map_location="cpu", weights_only=True)
    state_dict = checkpoint["state_dict"]
    params = _infer_params(state_dict)

    item_encoder = None
    if text_embeddings_path is None:
        text_embeddings_path = Path(settings.text_embeddings_path)
    else:
        text_embeddings_path = Path(text_embeddings_path)

    if text_embeddings_path.exists():
        item_encoder = TextItemEncoder.from_checkpoint(
            hidden_dim=params["hidden_dim"],
            path=text_embeddings_path,
        )
        logger.info("Loaded text embeddings from %s", text_embeddings_path)

    model = BERT4Rec(
        n_items=params["n_items"],
        max_len=params["max_len"],
        hidden_dim=params["hidden_dim"],
        num_heads=params["num_heads"],
        num_layers=params["num_layers"],
        item_encoder=item_encoder,
    )

    missing, unexpected = model.load_state_dict(state_dict, strict=False)
    if missing:
        logger.warning("Missing keys (init from scratch): %s", missing)
    if unexpected:
        logger.warning("Unexpected keys (ignored): %s", unexpected)

    device = _resolve_device(device)
    model.to(device).eval()

    logger.info(
        "Loaded checkpoint %s with n_items=%d max_len=%d on %s",
        ckpt_path,
        params["n_items"],
        params["max_len"],
        device,
    )
    return model, params["n_items"], params["max_len"]


def _infer_params(state_dict: dict[str, Tensor]) -> dict[str, int]:
    emb_shape = state_dict["item_embedding.weight"].shape
    hidden_dim = emb_shape[1]
    layer_indices = {
        int(key.split(".")[2])
        for key in state_dict
        if key.startswith("transformer.layers.") and ".self_attn." in key
    }

    # Prefer num_heads from checkpoint metadata, else infer from hidden_dim
    num_heads = _infer_num_heads(state_dict, hidden_dim)

    return {
        "n_items": emb_shape[0] - 2,
        "hidden_dim": hidden_dim,
        "max_len": state_dict["pos_embedding.weight"].shape[0],
        "num_layers": max(layer_indices) + 1 if layer_indices else 1,
        "num_heads": num_heads,
    }


def _infer_num_heads(state_dict: dict[str, Tensor], hidden_dim: int) -> int:
    # Check checkpoint metadata first (stored during training)
    if "_num_heads" in state_dict:
        return int(state_dict["_num_heads"])

    # Infer from in_proj_weight shape if available
    for key, tensor in state_dict.items():
        if "self_attn.in_proj_weight" in key and tensor.dim() == 2:
            # in_proj_weight has shape (3 * hidden_dim, hidden_dim)
            # The head dim must divide hidden_dim evenly
            for candidate in (2, 4, 8, 1, 3, 6, 12):
                if hidden_dim % candidate == 0:
                    return candidate
            break

    # Default fallback
    return 2


@torch.no_grad()
def predict(
    model: BERT4Rec,
    history: list[int],
    max_len: int,
    top_k: int = 10,
    device: Device | None = None,
) -> list[tuple[int, float]]:
    device = _resolve_device(device)
    model.to(device)

    seq = _pad_sequence(history + [model.mask_token], max_len)
    logits = model(torch.tensor([seq], dtype=torch.long, device=device))[0, -1, :]

    logits[0] = float("-inf")
    for item in history:
        if 0 <= item < logits.size(0):
            logits[item] = float("-inf")

    top_k = min(top_k, model.n_items)
    topk = torch.topk(logits, top_k)
    return [(idx.item(), score.item()) for score, idx in zip(topk.values, topk.indices)]


def recommend(
    model: BERT4Rec,
    history: list[int],
    max_len: int,
    top_k: int = 10,
    device: Device | None = None,
) -> list[dict[str, int | float]]:
    return [
        {"rank": rank, "item_idx": item_idx, "score": score}
        for rank, (item_idx, score) in enumerate(
            predict(model, history, max_len=max_len, top_k=top_k, device=device),
            start=1,
        )
    ]


def _pad_sequence(seq: list[int], max_len: int, pad_token: int = 0) -> list[int]:
    seq = seq[-max_len:]
    return [pad_token] * (max_len - len(seq)) + seq


if __name__ == "__main__":
    model, _, max_len = load_model(settings.model_checkpoint_path)
    history = [1, 2, 3]
    for item_idx, score in predict(model, history, max_len=max_len, top_k=10):
        print(f"Item idx: {item_idx}, Score: {score}")
