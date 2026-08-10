# Hướng dẫn cấu hình

## Biến môi trường

Tất cả biến môi trường được quản lý qua file `.env` (đọc bởi `python-dotenv`).

```bash
cp .env.example .env
```

### Danh sách biến

| Biên | Mặc định | Bắt buộc | Mô tả |
|------|----------|----------|-------|
| `APP_NAME` | `MARS Recommender API` | Không | Tên ứng dụng |
| `API_PREFIX` | `/api/v1` | Không | Prefix cho tất cả API routes |
| `ENVIRONMENT` | `development` | Không | Môi trường: `development` hoặc `production` |
| `JWT_SECRET_KEY` | *(auto-generated)* | Prod | Secret key để ký JWT tokens |
| `JWT_ALGORITHM` | `HS256` | Không | Thuật toán JWT |
| `ACCESS_TOKEN_EXPIRE_minutes` | `60` | Không | Thời gian hết hạn token (phút) |
| `CORS_ORIGINS` | `http://localhost:8000,http://127.0.0.1:8000` | Không | CORS allowed origins (phân tách bằng `,`) |
| `ADMIN_USERNAME` | `admin` | Không | Username admin seed |
| `ADMIN_PASSWORD` | *(random if empty)* | Prod | Password admin |
| `LEARNER_USERNAME` | `learner` | Không | Username learner seed |
| `LEARNER_PASSWORD` | *(random if empty)* | Prod | Password learner |
| `MODEL_CHECKPOINT_PATH` | `models/checkpoints/bert4rec.pt` | Không | Đường dẫn checkpoint BERT4Rec |
| `TEXT_EMBEDDINGS_PATH` | `models/sentence-camembert-base.pt` | Không | Đường dẫn text embeddings |
| `LOG_RETENTION_DAYS` | `30` | Không | Số ngày giữ log (auto-cleanup) |
| `DATABASE_URL` | `postgresql://...` | Không | PostgreSQL URL (chưa dùng) |
| `REDIS_URL` | `redis://localhost:6379/0` | Không | Redis URL (chưa dùng) |

### Biểu diễn chi tiết

#### JWT_SECRET_KEY

```bash
# Tạo secret key an toàn
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

**Production:** Bắt buộc phải đặt. Nếu không hoặc giữ giá trị mặc định, server sẽ raise `ValueError` khi khởi động.

**Development:** Tự động tạo random key nếu trống.

#### CORS_ORIGINS

```bash
# Cho phép nhiều origins
CORS_ORIGINS=http://localhost:8000,http://localhost:3000,https://myapp.com
```

#### ADMIN_PASSWORD / LEARNER_PASSWORD

**Production:** Bắt buộc phải đặt.

**Development:** Nếu trống, tự động generate random password và log ra console.

**Yêu cầu password:** Tối thiểu 8 ký tự, 1 chữ hoa, 1 chữ thường, 1 chữ số.

#### MODEL_CHECKPOINT_PATH

Đường dẫn tương đối từ root project. File phải tồn tại nếu muốn dùng BERT4Rec inference.

#### LOG_RETENTION_DAYS

Log older than N days sẽ tự động xóa khi server khởi động. Cũng có thể trigger thủ công qua `POST /admin/cleanup-logs`.

---

## Ví dụ file .env

### Development

```bash
ENVIRONMENT=development
ADMIN_USERNAME=admin
ADMIN_PASSWORD=Admin123
LEARNER_USERNAME=learner
LEARNER_PASSWORD=Learner123
LOG_RETENTION_DAYS=30
```

### Production

```bash
ENVIRONMENT=production
JWT_SECRET_KEY=<secret_key_from_secrets_module>
ADMIN_USERNAME=admin
ADMIN_PASSWORD=<strong_random_password>
LEARNER_USERNAME=learner
LEARNER_PASSWORD=<strong_random_password>
CORS_ORIGINS=https://myapp.com
LOG_RETENTION_DAYS=90
```

---

## Behavior theo môi trường

| Hành vi | Development | Production |
|---------|-------------|------------|
| JWT_SECRET | Auto-generate random | **Bắt buộc** từ env |
| Admin/Learner password | Auto-generate nếu trống | **Bắt buộc** từ env |
| Debug endpoint (`/debug/infer`) | Hoạt động | Trả 404 |
| Auto seed users | Có | Có |
| Auto cleanup logs | Có | Có |
