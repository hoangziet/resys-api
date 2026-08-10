import torch

from models.bert4rec import BERT4Rec, TextItemEncoder, resolve_artifact_path


def test_canonical_module_exports_model_and_helpers():
    assert BERT4Rec is not None


def test_text_encoder_and_model_can_be_instantiated_with_default_paths():
    embeddings = [[0.1, 0.2], [0.3, 0.4]]
    encoder = TextItemEncoder(embeddings=torch.tensor(embeddings), hidden_dim=2)
    assert encoder.text_proj.in_features == 2

    model = BERT4Rec(n_items=2, hidden_dim=4, num_heads=1, num_layers=1)
    assert model.n_items == 2


def test_artifact_paths_resolve_from_repo_root():
    resolved = resolve_artifact_path("models/checkpoints/bert4rec.pt")
    assert resolved.name == "bert4rec.pt"
    assert resolved.is_absolute()
