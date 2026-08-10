# MARS Recommender API

Hệ thống gợi ý khóa học trực tuyến sử dụng mô hình BERT4Rec (Bidirectional Encoder Representations from Transformers for Recommendation).

## Mô tả

MARS Recommender API cung cấp API RESTful để gợi ý khóa học cá nhân hóa cho người dùng. Hệ thống kết hợp nhiều chiến lược gợi ý:

- **BERT4Rec** — Mô hình deep learning dự đoán khóa học tiếp theo dựa trên lịch sử học tập
- **Vector Similarity** — Gợi ý tương đồng dựa trên embedding ngữ nghĩa (Sentence-CamemBERT)
- **Popularity-based** — Khóa học phổ biến nhất làm fallback

## Công nghệ

| Lớp | Công nghệ |
|------|-----------|
| Backend Framework | FastAPI 0.139+ |
| ML Model | PyTorch 2.6 (CUDA 12.4) |
| Text Embedding | Sentence-CamemBERT |
| Database | SQLite (dev) / PostgreSQL (prod) |
| Migration | Alembic + SQLAlchemy |
| Authentication | JWT (PyJWT) + bcrypt |
| Rate Limiting | slowapi |
| Package Manager | uv (Astral) |
| Container | Docker + Docker Compose |
| Frontend | Vanilla HTML/CSS/JS |

## Kiến trúc tóm tắt

```
Frontend (HTML/JS)
    ↓
FastAPI Server
    ↓
┌──────────────────────────────────┐
│  Auth  │  History  │  Recs  │ Admin │  ← API Routers
└──────────────────────────────────┘
    ↓                    ↓
SQLite/PostgreSQL    BERT4Rec Model
                     + Embeddings
```

## Cách chạy nhanh

```bash
# Clone
git clone <repo-url> && cd resys-api

# Cài dependencies
uv sync

# Tạo file .env
cp .env.example .env
# Chỉnh sửa .env với credentials thực

# Chạy server
uvicorn app:app --reload --port 8000
```

Truy cập http://localhost:8000 để sử dụng giao diện.

## Link tài liệu

| Tài liệu | Đường dẫn |
|----------|-----------|
| Kiến trúc hệ thống | [SYSTEM_ARCHITECTURE.md](./SYSTEM_ARCHITECTURE.md) |
| Cấu trúc dự án | [PROJECT_STRUCTURE.md](./PROJECT_STRUCTURE.md) |
| Hướng dẫn phát triển | [DEVELOPMENT_GUIDE.md](./DEVELOPMENT_GUIDE.md) |
| Tài liệu API | [API_DOCUMENTATION.md](./API_DOCUMENTATION.md) |
| Thiết kế Database | [DATABASE_DESIGN.md](./DATABASE_DESIGN.md) |
| Pipeline ML | [ML_PIPELINE.md](./ML_PIPELINE.md) |
| Hướng dẫn cấu hình | [CONFIGURATION_GUIDE.md](./CONFIGURATION_GUIDE.md) |
| Hướng dẫn triển khai | [DEPLOYMENT_GUIDE.md](./DEPLOYMENT_GUIDE.md) |
| Khắc phục sự cố | [TROUBLESHOOTING.md](./TROUBLESHOOTING.md) |
