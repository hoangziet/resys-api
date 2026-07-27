# Hướng dẫn triển khai

## Docker

### Dockerfile

Dockerfile sử dụng multi-stage build:

```dockerfile
# Stage 1: Builder — cài dependencies
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

# Stage 2: Runtime — chạy app
FROM python:3.12-slim-bookworm
WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"
COPY . .
EXPOSE 8000
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Build

```bash
docker build -t mars-recommender .
```

### Run

```bash
docker run -p 8000:8000 \
  -e JWT_SECRET_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(48))") \
  -e ADMIN_PASSWORD=Admin123 \
  -e LEARNER_PASSWORD=Learner123 \
  -v $(pwd)/data:/app/data \
  mars-recommender
```

---

## Docker Compose

### docker-compose.yml

```yaml
services:
  api:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - ./data:/app/data
    environment:
      - ENVIRONMENT=production
      - JWT_SECRET_KEY=${JWT_SECRET_KEY}
      - ADMIN_USERNAME=${ADMIN_USERNAME:-admin}
      - ADMIN_PASSWORD=${ADMIN_PASSWORD}
      - LEARNER_USERNAME=${LEARNER_USERNAME:-learner}
      - LEARNER_PASSWORD=${LEARNER_PASSWORD}
```

### Khởi chạy

```bash
# Tạo secret key
export JWT_SECRET_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(48))")

# Chạy
docker compose up --build -d

# Xem logs
docker compose logs -f api

# Dừng
docker compose down
```

---

## Production

### Yêu cầu

- Python 3.12+ (hoặc Docker)
- CUDA 12.4 (tùy chọn, dùng CPU nếu không có GPU)
- Ít nhất 2GB RAM (cho model + data)

### Uvicorn production

```bash
uvicorn app:app \
  --host 0.0.0.0 \
  --port 8000 \
  --workers 4 \
  --log-level info
```

**Lưu ý:** Với `--workers > 1`, mỗi worker sẽ load model riêng vào RAM. Nếu RAM hạn chế, dùng 1 worker.

---

## Nginx Reverse Proxy

### Cấu hình cơ bản

```nginx
server {
    listen 80;
    server_name myapp.com;

    # Redirect HTTP → HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl;
    server_name myapp.com;

    ssl_certificate /etc/ssl/certs/myapp.pem;
    ssl_certificate_key /etc/ssl/private/myapp.key;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # Proxy to FastAPI
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # WebSocket support (nếu cần)
    location /ws {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    # Static files cache
    location /assets/ {
        proxy_pass http://127.0.0.1:8000/assets/;
        expires 1h;
        add_header Cache-Control "public, immutable";
    }
}
```

### HTTPS

```bash
# Tự động với Certbot (Let's Encrypt)
sudo certbot --nginx -d myapp.com

# Hoặc self-signed (dev)
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout /etc/ssl/private/myapp.key \
  -out /etc/ssl/certs/myapp.pem
```

---

## Systemd Service

```ini
# /etc/systemd/system/mars-recommender.service
[Unit]
Description=MARS Recommender API
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/resys-api
Environment="PATH=/opt/resys-api/.venv/bin"
EnvironmentFile=/opt/resys-api/.env
ExecStart=/opt/resys-api/.venv/bin/uvicorn app:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable mars-recommender
sudo systemctl start mars-recommender
sudo systemctl status mars-recommender
```

---

## Logs

```bash
# Xem logs realtime
docker compose logs -f api

# Systemd logs
journalctl -u mars-recommender -f

# Uvicorn access logs
uvicorn app:app --log-level info 2>&1 | tee app.log
```

### Log levels

- `WARNING` — Startup warnings (missing env vars, generated passwords)
- `ERROR` — DB errors, inference failures
- `INFO` — Seed, cleanup, model load
- `DEBUG` — Request/response details (bật bằng `--log-level debug`)
