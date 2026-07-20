# Recommendation System Architecture

This document describes the neural and vector search models used in the MARS Recommender serving system.

## 1. BERT4Rec Neural Sequence Model

The primary recommender uses a bidirectional Transformer model (`BERT4Rec`) to model the sequential user interactions.

```
Input History Seq: [Course A, Course B, MASK]
      │
      ▼
Embedding Layer: Item Embeddings + Positional Embeddings
      │
      ▼
Transformer Blocks (Bidirectional Attention Layers)
      │
      ▼
MLM Prediction Head (Linear -> GELU -> LayerNorm)
      │
      ▼
Output Logits: Softmax probabilities over all courses (excluding padding/mask)
```

### Key Hyperparameters
- **Vocabulary Size (`vocab_size`)**: `n_items + 2` (pad token at index `0`, mask token at index `n_items + 1`).
- **Maximum Length (`max_len`)**: `50` (older courses are dropped if history length exceeds `max_len - 1`).
- **Hidden Dimensions (`hidden_dim`)**: `64`
- **Attention Heads (`num_heads`)**: `2`
- **Layers (`num_layers`)**: `2`

---

## 2. Text Embeddings & Similar Courses

For content-based similarity matching ("You May Also Like" and "Similar Courses"), we use dense vectors:

- **Source Model**: `sentence-camembert-base` (french semantic model).
- **Vectors Store**: `models/sentence-camembert-base.pt`.
- **Dimension**: `384`
- **Metric**: Cosine Similarity.
- **Workflow**:
  ```python
  # Normalize embeddings to unit length (L2 norm)
  norm_emb = F.normalize(embeddings, p=2, dim=1)
  # Matmul computes cosine similarity scores
  scores = torch.matmul(query_vec, norm_emb.T)
  ```

---

## 3. Fallback Strategies

If a user session has no learning history, or if model loaders raise exceptions:
1. **Empty History**: Fallback automatically routes requests to popularity score counts (trending courses rail).
2. **Missing Token Mapping**: The model ignores unknown course indices to prevent dictionary key errors.
