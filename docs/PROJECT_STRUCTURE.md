# Cấu trúc dự án

```
resys-api/
├── app.py                    # FastAPI application entry point
├── inference.py              # Model loading & prediction utilities
├── alembic.ini               # Alembic configuration
├── pyproject.toml            # Project dependencies (uv/pip)
├── uv.lock                   # Locked dependency versions
├── Dockerfile                # Multi-stage Docker build
├── docker-compose.yml        # Docker Compose config
│
├── api/                      # API route handlers
│   ├── auth.py               #   Authentication (register, login, me)
│   ├── courses.py            #   Course catalog (list, detail)
│   ├── history.py            #   Learning history CRUD
│   ├── recommendations.py    #   Recommendation endpoints
│   ├── admin.py              #   Admin dashboard & management
│   └── debug.py              #   Debug inference (dev only)
│
├── core/                     # Core infrastructure
│   ├── config.py             #   Settings & env var management
│   ├── security.py           #   JWT tokens & auth dependencies
│   ├── database.py           #   SQLite CRUD & connection management
│   ├── schema.py             #   SQLAlchemy MetaData (for Alembic)
│   └── rate_limit.py         #   slowapi limiter instance
│
├── models/                   # ML model & embeddings
│   ├── bert4rec.py           #   BERT4Rec model definition (PyTorch)
│   ├── embeddings.py         #   ItemEmbeddings: similarity, search, serialize
│   ├── sentence-camembert-base.pt  # Pre-computed text embeddings
│   └── checkpoints/
│       └── bert4rec.pt       #   Trained model checkpoint
│
├── assets/                   # Frontend static files
│   ├── index.html            #   Main SPA page
│   ├── app.js                #   Frontend JavaScript (state, API, rendering)
│   ├── style.css             #   Stylesheet
│   ├── thumbnail.png         #   Default thumbnail
│   └── video.mp4             #   Default video placeholder
│
├── data/                     # Data files (gitignored部分内容)
│   ├── db.sqlite3            #   SQLite database
│   └── processed/            #   ML pipeline outputs
│       ├── interactions/     #     User-item interaction logs
│       ├── item_features/    #     Item metadata + text embeddings
│       ├── mappings/         #     ID mappings (item_id, user_id)
│       ├── splits/           #     Train/val/test sequences
│       └── reports/          #     Preprocessing reports
│
├── alembic/                  # Database migrations
│   ├── env.py                #   Alembic environment config
│   ├── script.py.mako        #   Migration template
│   └── versions/             #   Migration files
│       ├── *_initial_schema.py
│       └── *_add_indexes.py
│
└── docs/                     # Documentation
    ├── README.md
    ├── SYSTEM_ARCHITECTURE.md
    ├── PROJECT_STRUCTURE.md
    ├── DEVELOPMENT_GUIDE.md
    ├── API_DOCUMENTATION.md
    ├── DATABASE_DESIGN.md
    ├── ML_PIPELINE.md
    ├── CONFIGURATION_GUIDE.md
    ├── DEPLOYMENT_GUIDE.md
    └── TROUBLESHOOTING.md
```

## Giải thích từng thư mục

### `api/`
Chứa các FastAPI router, mỗi file tương ứng một nhóm chức năng. Mỗi router định nghĩa các endpoint, nhận request, gọi `core/database.py` hoặc `models/` để xử lý, và trả về response.

### `core/`
Lõi hệ thống — quản lý cấu hình, bảo mật, kết nối database, rate limiting. Không chứa logic business, chỉ cung cấp infrastructure cho `api/` sử dụng.

### `models/`
Mô hình ML và dữ liệu embedding. `bert4rec.py` định kiến trúc BERT4Rec. `embeddings.py` quản lý item embeddings để similarity search và serialize metadata cho API.

### `assets/`
Frontend tĩnh — HTML, CSS, JavaScript. FastAPI mount thư mục này tại `/assets` và phục vụ `index.html` tại route gốc `/`.

### `data/`
Dữ liệu chạy runtime. `db.sqlite3` là database chính. `processed/` chứa output từ ML pipeline (embeddings, metadata CSV, train/val/test splits).

### `alembic/`
Database migrations quản lý bởi Alembic. `versions/` chứa các file migration theo thứ tự thời gian. Mỗi migration có `upgrade()` và `downgrade()` để thay đổi schema.

### `docs/`
Tài liệu dự án — kiến trúc, hướng dẫn phát triển, API, database, deployment, troubleshooting.
