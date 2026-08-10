# Hướng dẫn phát triển

## Yêu cầu

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (package manager)
- CUDA 12.4 (tùy chọn, dùng CPU nếu không có GPU)

## Clone project

```bash
git clone <repo-url>
cd resys-api
```

## Cài dependencies

```bash
uv sync
```

Sẽ tạo `.venv/` và cài tất cả dependencies từ `pyproject.toml` + `uv.lock`.

## Tạo file .env

```bash
cp .env.example .env
```

Chỉnh sửa `.env`:

```bash
ADMIN_USERNAME=admin
ADMIN_PASSWORD=your_secure_password_here
LEARNER_USERNAME=learner
LEARNER_PASSWORD=your_secure_password_here
```

Xem [CONFIGURATION_GUIDE.md](./CONFIGURATION_GUIDE.md) cho danh sách đầy đủ biến môi trường.

## Chạy backend

```bash
# Development (auto-reload)
uvicorn app:app --reload --port 8000

# Production
uvicorn app:app --host 0.0.0.0 --port 8000 --workers 4
```

Server sẽ:
1. Tạo database nếu chưa có (`data/db.sqlite3`)
2. Seed admin + learner accounts
3. Chạy Alembic migration (nếu DB đã có schema cũ)
4. Load BERT4Rec model vào RAM
5. Bắt đầu lắng nghe tại http://localhost:8000

## Chạy frontend

Frontend được phục vụ trực tiếp bởi FastAPI tại `http://localhost:8000/`. Không cần chạy server riêng.

Tất cả file frontend nằm trong `assets/`:
- `assets/index.html` — trang chính
- `assets/app.js` — JavaScript logic
- `assets/style.css` — styling

## Rebuild model

Nếu thay đổi kiến trúc model hoặc training lại:

```bash
# Training được thực hiện bên ngoài project này
# Sau khi training, copy checkpoint vào:
cp <new_checkpoint> models/checkpoints/bert4rec.pt
```

Model sẽ được load lại khi restart server.

## Rebuild embeddings

Nếu thay đổi sentence embedding model hoặc data:

```bash
# Embeddings được tạo bởi ML pipeline
# Output nằm trong data/processed/item_features/text_embeddings.pt
# Copy vào models/:
cp data/processed/item_features/text_embeddings.pt models/sentence-camembert-base.pt
```

## Seed database

Database tự động seed khi server khởi động lần đầu (nếu bảng `users` trống). Nếu muốn seed lại:

```bash
# Xóa database cũ
rm data/db.sqlite3

# Restart server — tự động seed
uvicorn app:app --reload
```

## Chạy database migrations

```bash
# Áp dụng migration mới nhất
alembic upgrade head

# Tạo migration mới từ thay đổi schema
alembic revision --autogenerate -m "mô tả thay đổi"

# Rollback 1 migration
alembic downgrade -1

# Rollback về đầu
alembic downgrade base

# Xem lịch sử migration
alembic history
```

## Chạy bằng Docker

```bash
# Build và chạy
docker compose up --build

# Chỉ build
docker compose build

# Dừng
docker compose down
```

## Pre-commit checks

```bash
# Kiểm tra syntax Python
python -m py_compile app.py
python -m py_compile inference.py
python -m py_compile core/database.py
python -m py_compile core/config.py
python -m py_compile core/security.py
python -m py_compile api/auth.py
python -m py_compile api/recommendations.py
python -m py_compile api/history.py
```
