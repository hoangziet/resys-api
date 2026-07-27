# ML Pipeline

## Tổng quan

```
Dataset (interactions.csv)
    ↓
Preprocessing (sequence generation)
    ↓
Vocabulary (item_id mapping)
    ↓
Text Embeddings (Sentence-CamemBERT)
    ↓
Training (BERT4Rec)
    ↓
Checkpoint (bert4rec.pt)
    ↓
Inference (inference.py)
    ↓
Recommendation (API response)
```

## Dataset

### Nguồn dữ liệu
- **`data/processed/interactions/interactions.csv`** — Log tương tác user-item
- **`data/processed/item_features/item_metadata.csv`** — Metadata khóa học (title, description, language, difficulty, theme, etc.)

### Preprocessing
Pipeline xử lý dữ liệu thô thành các file sẵn sàng cho training:

| File | Mô tả |
|------|-------|
| `data/processed/mappings/item_id_map.csv` | Ánh xạ `item_id` gốc → `item_idx` số nguyên |
| `data/processed/mappings/user_id_map.csv` | Ánh xạ `user_id` gốc → `user_idx` số nguyên |
| `data/processed/splits/train_sequences.csv` | Dãy khóa học train (80%) |
| `data/processed/splits/val_sequences.csv` | Dãy khóa học validation (10%) |
| `data/processed/splits/test_sequences.csv` | Dãy khóa học test (10%) |
| `data/processed/reports/dataset_stats.json` | Thống kê dataset |
| `data/processed/reports/preprocessing_report.json` | Báo cáo preprocessing |

### Vocabulary
- Số lượng item (`n_items`) = số item trong `item_id_map.csv`
- Item index bắt đầu từ 1 (0 = padding token)
- Mask token = `n_items + 1`
- Vocab size = `n_items + 2`

## Text Embeddings

### Cách tạo
1. Lấy `title` + `description` từ `item_metadata.csv`
2. Encode bằng **Sentence-CamemBERT** (mô hình French BERT)
3. Lưu tensor shape `(n_items, embedding_dim)` vào file `.pt`

### Checkpoint chứa gì

File `models/sentence-camembert-base.pt` chứa một PyTorch tensor:
- **Shape:** `(n_items, 768)` — 768 chiều từ Sentence-CamemBERT
- **Type:** `torch.float32`
- **Norm:** Chưa normalize (sẽ normalize khi dùng cho similarity)

### Cách dùng trong inference

```python
# models/embeddings.py — ItemEmbeddings
self.embeddings = torch.load(path)           # Load raw embeddings
self.normalized_embeddings = F.normalize(self.embeddings, p=2, dim=1)  # L2 normalize
```

Embeddings được dùng cho:
- **Similarity search:** Cosine similarity = dot product của normalized vectors
- **Item encoding:** `TextItemEncoder` project từ 768 → `hidden_dim` (64) qua Linear layer

## BERT4Rec Model

### Kiến trúc

```
Input: item sequence [item_1, item_2, ..., mask_token]
    ↓
Item Embedding (vocab_size × hidden_dim)
    ↓ (+)
Position Embedding (max_len × hidden_dim)
    ↓ (+)
Watch Embedding (optional, training only)
    ↓
LayerNorm → Dropout
    ↓
Transformer Encoder (num_layers × Multi-Head Self-Attention)
    ↓
FFN → LayerNorm (MLM prediction head)
    ↓
Weight-tied Linear Projection → Softmax
    ↓
Output: probability distribution over all items
```

### Hyperparameters

| Parameter | Giá trị | Mô tả |
|-----------|---------|-------|
| `n_items` | Từ checkpoint | Số lượng khóa học |
| `max_len` | Từ checkpoint | Chiều dài sequence tối đa (thường 50) |
| `hidden_dim` | Từ checkpoint | Kích thước hidden (thường 64) |
| `num_heads` | Từ checkpoint | Số attention heads (thường 2) |
| `num_layers` | Từ checkpoint | Số transformer layers (thường 2) |
| `dropout` | 0.2 | Dropout rate |

### Checkpoint file

File `models/checkpoints/bert4rec.pt` chứa:

```python
{
    "state_dict": {
        "item_embedding.weight": Tensor(n_items+2, hidden_dim),
        "pos_embedding.weight": Tensor(max_len, hidden_dim),
        "transformer.layers.0.self_attn.in_proj_weight": Tensor(3*hidden_dim, hidden_dim),
        "transformer.layers.0.self_attn.in_proj_bias": Tensor(3*hidden_dim),
        # ... (các weight khác)
    }
}
```

## Inference

### Model Loading (`inference.py`)

```python
model, n_items, max_len = load_model("models/checkpoints/bert4rec.pt")
```

Quy trình:
1. Load checkpoint với `torch.load(path, weights_only=True)`
2. Infer hyperparameters từ state_dict (`_infer_params`)
3. Optionally load `TextItemEncoder` từ embeddings file
4. Instantiate `BERT4Rec` model
5. Load state_dict (strict=False, log missing/unexpected keys)
6. Move to device (CUDA nếu có, else CPU)
7. Set eval mode

### Prediction

```python
# Input: lịch sử học tập [1, 2, 3]
# Model: append mask_token, left-pad to max_len
# Output: logits cho tất cả items
# Filter: -inf cho padding + items đã học
# Return: top-k (item_idx, score)
```

### Fallback mechanism

Nếu model không available hoặc inference lỗi:
1. **`for-you`** → Fallback sang `popular_fallback_error` (lấy khóa học phổ biến)
2. **`you-may-also-like`** → Fallback sang `popular_fallback_error`
3. **`similar/{id}`** → Fallback sang `popular_fallback_error`

Mọi fallback đều được log bằng `logger.exception()` với context.
