# Thiết kế Database

## ER Diagram

```
┌─────────────────────┐       ┌──────────────────────────┐
│       users          │       │      user_history         │
├─────────────────────┤       ├──────────────────────────┤
│ id (PK, INTEGER)    │──┐    │ user_id (FK → users.id)  │
│ username (TEXT, UQ)  │  │    │ item_idx (INTEGER)        │
│ password_hash (TEXT) │  ├───>│ order_idx (INTEGER)       │
│ role (TEXT)          │  │    │ added_at (DATETIME)       │
└─────────────────────┘  │    └──────────────────────────┘
                          │
                          │    ┌──────────────────────────┐
                          │    │   recommendation_logs     │
                          │    ├──────────────────────────┤
                          │    │ id (PK, INTEGER)          │
                          │    │ timestamp (DATETIME)      │
                          │    │ username (TEXT)            │
                          │    │ strategy (TEXT)            │
                          │    │ latency_ms (FLOAT)         │
                          │    │ history (TEXT)              │
                          │    │ results (TEXT)              │
                          │    └──────────────────────────┘
                          │
                     ON DELETE CASCADE
```

## Schema chi tiết

### `users`

Bảng lưu thông tin tài khoản người dùng.

```sql
CREATE TABLE users (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    username    TEXT    UNIQUE NOT NULL,
    password_hash TEXT  NOT NULL,
    role        TEXT    NOT NULL DEFAULT 'learner'
);
```

| Cột | Kiểu | Ràng buộc | Mô tả |
|-----|------|-----------|-------|
| `id` | INTEGER | PK, AUTOINCREMENT | ID tự tăng |
| `username` | TEXT | UNIQUE, NOT NULL | Tên đăng nhập |
| `password_hash` | TEXT | NOT NULL | Mật khẩu mã hóa (bcrypt) |
| `role` | TEXT | NOT NULL, DEFAULT 'learner' | Vai trò: `learner` hoặc `admin` |

---

### `user_history`

Bảng lưu lịch sử khóa học đã học. Composite primary key `(user_id, item_idx)` đảm bảo mỗi người dùng chỉ có 1 bản ghi mỗi khóa học.

```sql
CREATE TABLE user_history (
    user_id   INTEGER  NOT NULL,
    item_idx  INTEGER  NOT NULL,
    order_idx INTEGER  NOT NULL DEFAULT 0,
    added_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, item_idx),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
```

| Cột | Kiểu | Ràng buộc | Mô tả |
|-----|------|-----------|-------|
| `user_id` | INTEGER | FK → users.id, NOT NULL | ID người dùng |
| `item_idx` | INTEGER | NOT NULL | Chỉ số khóa học |
| `order_idx` | INTEGER | NOT NULL, DEFAULT 0 | Thứ tự thêm vào (giữ nguyên interaction ordering) |
| `added_at` | DATETIME | DEFAULT CURRENT_TIMESTAMP | Thời gian thêm |

---

### `recommendation_logs`

Bảng lưu log mọi request gợi ý để audit và phân tích.

```sql
CREATE TABLE recommendation_logs (
    id         INTEGER  PRIMARY KEY AUTOINCREMENT,
    timestamp  DATETIME DEFAULT CURRENT_TIMESTAMP,
    username   TEXT,
    strategy   TEXT     NOT NULL,
    latency_ms REAL     NOT NULL,
    history    TEXT,
    results    TEXT
);
```

| Cột | Kiểu | Ràng buộc | Mô tả |
|-----|------|-----------|-------|
| `id` | INTEGER | PK, AUTOINCREMENT | ID tự tăng |
| `timestamp` | DATETIME | DEFAULT CURRENT_TIMESTAMP | Thời gian request |
| `username` | TEXT | NULLABLE | Tên người dùng (NULL nếu anonymous) |
| `strategy` | TEXT | NOT NULL | Chiến lược: `bert4rec_personalized`, `vector_similarity`, `popularity_nb_views`, `popular_fallback_error` |
| `latency_ms` | REAL | NOT NULL | Thời gian xử lý (ms) |
| `history` | TEXT | NULLABLE | Lịch sử đầu vào, dạng CSV: `"1,2,3"` |
| `results` | TEXT | NULLABLE | Kết quả đầu ra, dạng CSV: `"87,42,15"` |

---

## Foreign Keys

| Bảng | Cột | References | On Delete |
|------|-----|-----------|-----------|
| `user_history` | `user_id` | `users.id` | CASCADE |

Khi xóa một user, tất cả bản ghi `user_history` liên quan tự động bị xóa.

**Lưu ý:** SQLite tắt FK enforcement theo mặc định. Hệ thống bật bằng `PRAGMA foreign_keys = ON` trên mỗi connection (`core/database.py`).

---

## Indexes

### Indexes có sẵn (tự tạo bởi PRIMARY KEY / UNIQUE)

| Index | Bảng | Cột | Loại |
|-------|------|-----|------|
| `sqlite_autoindex_users_1` | `users` | `username` | UNIQUE |
| `sqlite_autoindex_user_history_1` | `user_history` | `(user_id, item_idx)` | PRIMARY KEY |

### Indexes tùy chỉnh (tạo bởi Alembic migration)

| Tên index | Bảng | Cột | Mục đích |
|-----------|------|-----|----------|
| `ix_rec_logs_timestamp` | `recommendation_logs` | `timestamp` | Query `ORDER BY timestamp DESC` |
| `ix_rec_logs_username` | `recommendation_logs` | `username` | Filter theo user |
| `ix_rec_logs_strategy` | `recommendation_logs` | `strategy` | Filter theo strategy |

---

## Migration

Hệ thống sử dụng Alembic để quản lý schema migrations.

### Cấu trúc

```
alembic/
├── env.py              # Cấu hình Alembic (SQLAlchemy engine, MetaData)
├── script.py.mako      # Template cho migration mới
└── versions/
    ├── c31f53b0d12f_initial_schema.py    # Tạo 3 bảng ban đầu
    └── a0882f19c5b2_add_indexes.py       # Thêm indexes cho recommendation_logs
```

### Lệnh thường dùng

```bash
# Áp dụng migration mới nhất
alembic upgrade head

# Tạo migration mới (auto-detect từ core/schema.py)
alembic revision --autogenerate -m "mô tả"

# Rollback 1 bước
alembic downgrade -1

# Xem lịch sử
alembic history
```

### Schema source of truth

`core/schema.py` chứa SQLAlchemy MetaData definitions — đây là nguồn gốc để Alembic auto-generate migration. Khi thay đổi schema, sửa file này trước, sau đó chạy `alembic revision --autogenerate`.
