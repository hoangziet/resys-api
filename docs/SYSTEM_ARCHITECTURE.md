# Kiến trúc hệ thống

## Mô tả tổng quan

MARS Recommender API là hệ thống microservice đơn (monolithic API) phục vụ cả frontend và backend. Hệ thống quản lý xác thực người dùng, lịch sử học tập, và cung cấp gợi ý khóa học cá nhân hóa thông qua mô hình BERT4Rec.

## Các module chính

```
┌─────────────────────────────────────────────────────────┐
│                     Frontend                             │
│              assets/index.html + app.js                   │
└──────────────────────────┬──────────────────────────────┘
                           │ HTTP/REST
                           ▼
┌─────────────────────────────────────────────────────────┐
│                    FastAPI Server                         │
│  ┌──────────┬──────────┬──────────┬──────────┬────────┐ │
│  │ auth.py  │history.py│ recs.py  │admin.py  │debug.py│ │
│  └────┬─────┴────┬─────┴────┬─────┴────┬─────┴────┬───┘ │
│       │          │          │          │          │       │
│  ┌────▼──────────▼──────────▼──────────▼──────────▼───┐ │
│  │              core/ (config, security, db)           │ │
│  └────┬──────────┬────────────────────┬───────────────┘ │
└───────┼──────────┼────────────────────┼─────────────────┘
        │          │                    │
        ▼          ▼                    ▼
   ┌─────────┐ ┌──────────────┐  ┌───────────────┐
   │ SQLite/ │ │ BERT4Rec     │  │ Sentence-     │
   │ Postgres│ │ Model        │  │ CamemBERT     │
   │         │ │ (PyTorch)    │  │ Embeddings    │
   └─────────┘ └──────────────┘  └───────────────┘
```

## Mô tả từng module

### Frontend (`assets/`)
- Giao diện SPA (Single Page Application) vanilla HTML/CSS/JS
- Tự động chuyển tab: Dashboard, Search, History, Admin
- Gọi API qua `fetch()` với JWT Bearer token

### FastAPI Server (`app.py` + `api/`)
- **app.py** — Factory function `create_app()`: khởi tạo DB, load model, đăng ký routers
- **api/auth.py** — Đăng ký, đăng nhập, xác thực JWT
- **api/history.py** — CRUD lịch sử học tập
- **api/recommendations.py** — Gợi ý khóa học (BERT4Rec, similarity, popularity)
- **api/admin.py** — Quản trị: model health, logs, cleanup
- **api/debug.py** — Debug inference (chỉ dev mode)

### Core Layer (`core/`)
- **config.py** — `Settings` dataclass từ env vars, validate production
- **security.py** — JWT create/verify, `require_admin` dependency
- **database.py** — SQLite CRUD, connection management, bcrypt hashing
- **schema.py** — SQLAlchemy MetaData cho Alembic migrations
- **rate_limit.py** — slowapi limiter instance

### Recommendation Service (`inference.py` + `models/`)
- **inference.py** — Load checkpoint, infer hyperparams, predict, recommend
- **models/bert4recpy.py** — BERT4Rec nn.Module + TextItemEncoder
- **models/embeddings.py** — ItemEmbeddings: similarity search, serialize, search

### Data Layer (`data/`)
- **db.sqlite3** — SQLite database (users, history, logs)
- **processed/** — ML pipeline outputs (embeddings, metadata, splits)

## Phụ thuộc giữa các module

```
app.py
  ├── api/auth.py ──────→ core/security.py
  │                       core/database.py
  │                       core/config.py
  ├── api/history.py ───→ core/database.py
  │                       models/embeddings.py
  ├── api/recommendations.py → inference.py
  │                             core/database.py
  │                             models/embeddings.py
  ├── api/admin.py ─────→ core/database.py
  │                       core/config.py
  ├── api/debug.py ─────→ inference.py
  └── core/database.py ─→ core/config.py

inference.py
  ├── models/bert4recpy.py (BERT4Rec, TextItemEncoder)
  ├── core/config.py
  └── torch

models/embeddings.py
  ├── torch
  └── data/processed/ (CSV, PT files)
```

## Sơ đồ request flow

```
1. User → POST /api/v1/auth/token (login)
   → Verify password (bcrypt)
   → Return JWT token

2. User → POST /api/v1/recommendations/for-you (with JWT)
   → Verify JWT → Get user history from DB
   → Load BERT4Rec model (cached in memory)
   → Run inference → Return top-k items
   → Log to recommendation_logs table

3. User → POST /api/v1/recommendations/you-may-also-like
   → Get last item from history
   → Compute cosine similarity with all item embeddings
   → Return top-k similar items
```

## Middleware

| Middleware | Mục đích |
|-----------|----------|
| `CORSMiddleware` | Cross-origin request handling |
| `CacheControlMiddleware` | Cache-Control header cho recommendations |
| `slowapi` | Rate limiting (5/sec cho recommendations) |
