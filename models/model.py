"""
bert4rec.py
===========
BERT4Rec — masked item prediction for sequential recommendation.

Architecture:
    - Bidirectional Transformer encoder
    - Input LayerNorm applied after embedding sum (before dropout), matching BERT paper
    - Masked item modeling (15% random mask during training)
    - MLM prediction head: Linear → GELU → LayerNorm (BERT-style)
    - Weight-tied output projection with per-item bias
    - Special mask_token = n_items + 1
"""

import torch
import torch.nn as nn
import torch.nn.functional as F


class BERT4Rec(nn.Module):
    def __init__(self, n_items, max_len=50, hidden_dim=64, num_heads=2,
                 num_layers=2, dropout=0.2,
                 watch_mode="none", watch_num_bins=5, watch_alpha=1.0,
                 item_encoder=None):
        super().__init__()
        self.n_items = n_items
        self.hidden_dim = hidden_dim
        self.pad_token = 0
        self.mask_token = n_items + 1
        self.vocab_size = n_items + 2
        self.watch_mode = watch_mode
        self.watch_alpha = float(watch_alpha)
        self.watch_num_bins = int(watch_num_bins)
        self.item_encoder = item_encoder

        self.item_embedding = nn.Embedding(self.vocab_size, hidden_dim, padding_idx=0)
        self.pos_embedding = nn.Embedding(max_len, hidden_dim)

        # watch embedding: pad(0) + mask(1) + num_bins engagement bins
        self.watch_embedding = nn.Embedding(watch_num_bins + 2, hidden_dim, padding_idx=0)

        # mask token embedding for item_encoder path
        self.mask_embedding = nn.Embedding(1, hidden_dim)

        self.input_ln = nn.LayerNorm(hidden_dim, eps=1e-12)
        self.dropout = nn.Dropout(dropout)

        encoder_layer = nn.TransformerEncoderLayer(
            d_model=hidden_dim,
            nhead=num_heads,
            dim_feedforward=hidden_dim * 4,
            dropout=dropout,
            batch_first=True,
            activation="gelu",
        )
        self.transformer = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)

        self.pred_ffn = nn.Linear(hidden_dim, hidden_dim)
        self.pred_ln  = nn.LayerNorm(hidden_dim, eps=1e-12)

        self.out_bias = nn.Parameter(torch.zeros(n_items))

        self._init_weights()

    def _init_weights(self):
        nn.init.normal_(self.item_embedding.weight, std=0.02)
        nn.init.normal_(self.pos_embedding.weight, std=0.02)
        nn.init.normal_(self.pred_ffn.weight, std=0.02)
        nn.init.zeros_(self.pred_ffn.bias)
        nn.init.ones_(self.input_ln.weight)
        nn.init.zeros_(self.input_ln.bias)
        nn.init.ones_(self.pred_ln.weight)
        nn.init.zeros_(self.pred_ln.bias)
        nn.init.normal_(self.watch_embedding.weight, std=0.02)
        nn.init.normal_(self.mask_embedding.weight, std=0.02)
        with torch.no_grad():
            self.item_embedding.weight[0].zero_()
            self.watch_embedding.weight[0].zero_()

    def _item_input_embedding(self, input_seq: torch.Tensor) -> torch.Tensor:
        if self.item_encoder is None:
            return self.item_embedding(input_seq)
        real_ids = input_seq.clamp(max=self.n_items)
        encoded = self.item_encoder(real_ids)
        mask_token_mask = (input_seq == self.mask_token).unsqueeze(-1)
        mask_emb = self.mask_embedding.weight[0].view(1, 1, -1)
        encoded = torch.where(mask_token_mask, mask_emb, encoded)
        return encoded

    def forward(self, input_seq, watch_input_ids=None):
        B, L = input_seq.shape
        pos_ids = torch.arange(L, device=input_seq.device).unsqueeze(0).expand(B, L)
        x = self._item_input_embedding(input_seq) + self.pos_embedding(pos_ids)

        # ponytail: watch embeddings are a training-time augmentation only.
        # At inference (watch_input_ids=None), the model runs on base item+position
        # representations, analogous to how dropout is disabled at eval time.
        if self.watch_mode in {"embedding", "both"} and watch_input_ids is not None:
            x = x + self.watch_embedding(watch_input_ids)

        x = self.input_ln(x)   # LayerNorm before dropout (BERT convention)
        x = self.dropout(x)

        padding_mask = (input_seq == self.pad_token)
        x = self.transformer(x, src_key_padding_mask=padding_mask)

        # MLM prediction head: transform hidden states before weight-tied projection
        x = F.gelu(self.pred_ffn(x))
        x = self.pred_ln(x)

        # Output logits cover only padding (col 0) + real items (cols 1..n_items).
        # The MASK token (index n_items+1) is an input-only token, not an output class.
        real_item_weight = self.item_embedding.weight[1 : self.n_items + 1]
        real_item_logits = F.linear(x, real_item_weight, self.out_bias)

        padding_logits = torch.zeros(
            *real_item_logits.shape[:-1], 1,
            dtype=real_item_logits.dtype, device=real_item_logits.device,
        )
        return torch.nan_to_num(
            torch.cat([padding_logits, real_item_logits], dim=-1),
            nan=float("-inf"),
        )

    def loss(self, input_seq, labels, engagement=None, watch_input_ids=None):
        logits = self.forward(input_seq, watch_input_ids=watch_input_ids)

        valid_mask = labels.ne(self.pad_token)
        if not valid_mask.any():
            return torch.zeros((), device=input_seq.device, requires_grad=True)

        valid_labels = labels[valid_mask]
        if torch.any((valid_labels < 1) | (valid_labels > self.n_items)):
            raise ValueError(
                f"BERT4Rec labels must be real item IDs in [1, {self.n_items}]"
            )

        real_item_logits = logits[..., 1:][valid_mask]
        zero_based_labels = valid_labels - 1
        per_token = F.cross_entropy(real_item_logits, zero_based_labels, reduction="none")

        if self.watch_mode in {"loss", "both"} and engagement is not None:
            weights = 1.0 + self.watch_alpha * engagement[valid_mask].clamp(0.0, 1.0)
            return (weights * per_token).sum() / weights.sum().clamp_min(1e-12)
        return per_token.mean()


def get_model(n_items, **kwargs):
    return BERT4Rec(n_items=n_items, **kwargs)
