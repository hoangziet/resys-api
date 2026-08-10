# Khắc phục sự cố

## ModuleNotFoundError

```
ModuleNotFoundError: No module named 'bcrypt'
```

**Nguyên nhân:** Chưa cài dependencies hoặc chưa activate virtual environment.

**Giải pháp:**
```bash
# Cài dependencies
uv sync

# Activate venv
source .venv/bin/activate  # Linux/Mac
.venv\Scripts\activate     # Windows

# Verify
python -c "import bcrypt; print('OK')"
```

---

## Model not found

```
FileNotFoundError: Checkpoint not found: models/checkpoints/bert4rec.pt
```

**Nguyên nhân:** File checkpoint không tồn tại.

**Giải pháp:**
```bash
# Kiểm tra file có tồn tại không
ls -la models/checkpoints/bert4rec.pt

# Nếu chưa có, copy từ nguồn
cp /path/to/bert4rec.pt models/checkpoints/bert4rec.pt
```

**Lưu ý:** Server vẫn khởi động được — inference sẽ dùng popularity fallback thay vì BERT4Rec.

---

## Database locked

```
sqlite3.OperationalError: database is locked
```

**Nguyên nhân:** SQLite không hỗ trợ concurrent writes. Một process khác đang ghi database.

**Giải pháp:**
```bash
# Kiểm tra process đang dùng DB
lsof data/db.sqlite3

# Nếu dùng Docker, đảm bảo data/ không bị mount đồng thời
docker compose down
docker compose up

# Hoặc giảm WAL timeout
# Trong core/database.py, thêm vào get_connection():
# conn.execute("PRAGMA busy_timeout = 5000")
```

**Nâng cấp:** Với production cần concurrent access, chuyển sang PostgreSQL.

---

## CUDA unavailable

```
WARNING: CUDA not available, using CPU
```

**Nguyên nhân:** PyTorch không tìm thấy CUDA toolkit hoặc GPU không hỗ trợ.

**Giải pháp:**
```bash
# Kiểm tra CUDA
python -c "import torch; print(torch.cuda.is_available())"

# Nếu False, cài PyTorch CUDA version
pip install torch==2.6.0+cpu --index-url https://download.pytorch.org/whl/cpu

# Hoặc chấp nhận CPU (chậm hơn ~10x)
# Server sẽ tự động fallback sang CPU
```

---

## Checkpoint mismatch

```
WARNING: Missing keys (init from scratch): [...]
WARNING: Unexpected keys (ignored): [...]
```

**Nguyên nhân:** Checkpoint được train với kiến trúc khác (khác `hidden_dim`, `num_layers`, `num_heads`).

**Giải pháp:**
```bash
# Kiểm tra hyperparameters trong checkpoint
python -c "
import torch
ckpt = torch.load('models/checkpoints/bert4rec.pt', weights_only=True)
sd = ckpt['state_dict']
for k, v in sd.items():
    print(f'{k}: {v.shape}')
"
```

**So sánh** output với model definition trong `models/bert4recpy.py` để đảm bảo khớp.

---

## Port already used

```
ERROR: [Errno 10048] error while attempting to bind on address ('0.0.0.0', 8000)
```

**Nguyên nhân:** Port 8000 đang được process khác sử dụng.

**Giải pháp:**
```bash
# Tìm process đang dùng port 8000
lsof -i :8000          # Linux/Mac
netstat -ano | findstr :8000  # Windows

# Kill process
kill -9 <PID>

# Hoặc dùng port khác
uvicorn app:app --port 8001
```

---

## JWT invalid

```
401 Unauthorized: Could not validate credentials
```

**Nguyên nhân phổ biến:**
1. Token đã hết hạn
2. Token được ký với `JWT_SECRET_KEY` khác
3. Token malformed

**Giải pháp:**
```bash
# Kiểm tra JWT_SECRET_KEY
grep JWT_SECRET_KEY .env

# Decode JWT để xem payload
python -c "
import jwt
token = 'eyJhbGci...'
# Cần cùng secret key đã dùng khi tạo token
payload = jwt.decode(token, 'your-secret-key', algorithms=['HS256'])
print(payload)
"
```

**Lưu ý:** Khi thay đổi `JWT_SECRET_KEY`, tất cả token cũ sẽ không hợp lệ. User cần đăng nhập lại.

---

## Embedding missing

```
FileNotFoundError: Text embedding checkpoint not found
```

**Nguyên nhân:** File `models/sentence-camembert-base.pt` không tồn tại.

**Giải pháp:**
```bash
# Kiểm tra file
ls -la models/sentence-camembert-base.pt

# Nếu chưa có, copy từ processed data
cp data/processed/item_features/text_embeddings.pt models/sentence-camembert-base.pt
```

**Lưu ý:** Server vẫn hoạt động — similarity search sẽ không khả dụng, dùng popularity fallback.

---

## bcrypt incompatibility

```
ValueError: 'passlib' is not compatible with 'bcrypt' >= 5.0
```

**Nguyên nhân:** Thư viện `passlib` không tương thích với `bcrypt` 5.x.

**Giải pháp:** Dự án đã chuyển sang dùng `bcrypt` trực tiếp (bỏ `passlib`). Đảm bảo `pyproject.toml` không có `passlib` trong dependencies.

```bash
# Verify
grep passlib pyproject.toml  # Không nên có
```

---

## Alembic migration conflict

```
alembic.util.exc.CommandError: Can't locate revision identified by 'xxxxx'
```

**Nguyên nhân:** File migration bị thiếu hoặc `alembic_version` table bị corrupt.

**Giải pháp:**
```bash
# Xem version hiện tại
python -c "
import sqlite3
conn = sqlite3.connect('data/db.sqlite3')
print(conn.execute('SELECT * FROM alembic_version').fetchall())
conn.close()
"

# Reset — xóa DB và chạy lại từ đầu
rm data/db.sqlite3
alembic upgrade head
```
