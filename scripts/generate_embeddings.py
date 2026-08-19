"""Generate text embeddings for courses that do not have one yet.

Why this is an offline job: the recommendation stack ships a *pre-generated*
tensor (``models/sentence-camembert-base.pt``, one row per item_idx) and the
encoder that produced it, ``dangvantuan/sentence-camembert-base``, is not a
runtime dependency. Creating a course therefore cannot embed it synchronously -
the course is stored with ``embedding_status='pending'`` and stays out of
text-similarity recommendations until this job runs.

    uv sync --extra embeddings          # installs sentence-transformers
    python -m scripts.generate_embeddings

The tensor is addressed positionally: row N holds item_idx N, with row 0 reserved
as the padding row. New courses get ``MAX(item_idx) + 1``, so pending rows append
contiguously; the job refuses to write if that invariant is broken, because a
misaligned row would silently return the wrong course's neighbours.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

import torch

from core import database
from core.config import settings

log = logging.getLogger(__name__)

ENCODER_NAME = "dangvantuan/sentence-camembert-base"
MANIFEST_PATH = Path("data/processed/item_features/text_embeddings_manifest.json")


def _load_encoder(model_name: str):
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:  # pragma: no cover - depends on optional extra
        raise RuntimeError(
            "sentence-transformers is not installed. Install the optional extra "
            "with: uv sync --extra embeddings"
        ) from exc
    log.info("Loading encoder %s", model_name)
    return SentenceTransformer(model_name)


def _course_text(row: dict) -> str:
    """Text fed to the encoder, matching how the original tensor was built."""
    return (row.get("text") or row.get("title") or "").strip()


def generate_pending_embeddings(
    *,
    embeddings_path: Path | None = None,
    model_name: str = ENCODER_NAME,
    dry_run: bool = False,
) -> dict:
    """Embed every pending course and append it to the tensor.

    Returns a summary dict. Safe to re-run: courses already marked ready are
    skipped, so an interrupted run resumes cleanly.
    """
    embeddings_path = Path(embeddings_path or settings.text_embeddings_path)
    if not embeddings_path.exists():
        raise FileNotFoundError(f"Text embedding tensor not found: {embeddings_path}")

    pending = database.get_courses_pending_embedding()
    if not pending:
        return {"pending_courses": 0, "embedded": 0, "detail": "nothing to do"}

    tensor = torch.load(embeddings_path, map_location="cpu", weights_only=True)
    next_row = tensor.size(0)

    # Positional addressing: the first pending course must land on the next row.
    ordered = sorted(pending, key=lambda row: int(row["item_idx"]))
    expected = [next_row + offset for offset in range(len(ordered))]
    actual = [int(row["item_idx"]) for row in ordered]
    if actual != expected:
        raise RuntimeError(
            "Pending item_idx values are not contiguous with the embedding tensor. "
            f"Tensor has {next_row} rows so the next item_idx must be {next_row}, "
            f"but pending courses are {actual}. Refusing to write a misaligned "
            "tensor - every row must equal its item_idx."
        )

    texts = [_course_text(row) for row in ordered]
    if any(not text for text in texts):
        raise RuntimeError("Some pending courses have no text to embed")

    if dry_run:
        return {
            "pending_courses": len(ordered),
            "embedded": 0,
            "would_embed_item_idxs": actual,
            "dry_run": True,
        }

    encoder = _load_encoder(model_name)
    vectors = encoder.encode(texts, convert_to_numpy=True, show_progress_bar=False)
    new_rows = torch.tensor(vectors, dtype=tensor.dtype)

    if new_rows.size(1) != tensor.size(1):
        raise RuntimeError(
            f"Encoder produced {new_rows.size(1)}-d vectors but the tensor is "
            f"{tensor.size(1)}-d. Wrong encoder for this artifact?"
        )

    updated = torch.cat([tensor, new_rows], dim=0)
    torch.save(updated, embeddings_path)
    log.info(
        "Appended %d embeddings to %s (%d -> %d rows)",
        len(ordered),
        embeddings_path,
        tensor.size(0),
        updated.size(0),
    )

    _update_manifest(updated)
    marked = database.mark_embeddings_ready(actual)

    return {
        "pending_courses": len(ordered),
        "embedded": len(ordered),
        "item_idxs": actual,
        "marked_ready": marked,
        "tensor_rows": updated.size(0),
        "restart_required": True,
        "detail": (
            "Embeddings appended. Restart the API so ItemEmbeddings reloads the "
            "tensor before the new courses appear in similarity results."
        ),
    }


def _update_manifest(tensor: torch.Tensor) -> None:
    """Keep the manifest's shape/n_items in step with the tensor."""
    if not MANIFEST_PATH.exists():
        return
    try:
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        log.warning("Could not read %s; leaving it untouched", MANIFEST_PATH)
        return

    manifest["shape"] = list(tensor.shape)
    manifest["n_items"] = tensor.size(0) - 1
    # The stored hashes described the CSV-built tensor and no longer apply.
    manifest["appended_by"] = "scripts/generate_embeddings.py"
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would be embedded without loading the encoder",
    )
    parser.add_argument("--model", default=ENCODER_NAME, help="Encoder model name")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    result = generate_pending_embeddings(model_name=args.model, dry_run=args.dry_run)
    for key, value in result.items():
        print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
