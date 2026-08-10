# CI/CD Guide

## Pipeline

The GitHub Actions workflow lives at `.github/workflows/ci-cd.yml`.

It runs:

1. `uv sync --frozen --dev`
2. `uv run ruff check .`
3. `uv run pytest -q`
4. `docker build`
5. SSH deploy to the VPS on pushes to `develop`

## Required GitHub Secrets

Set these in GitHub repository settings:

- `VPS_HOST`: VPS public IP or domain
- `VPS_USER`: SSH user, for example `ubuntu`
- `VPS_SSH_KEY`: private key allowed to SSH into the VPS
- `VPS_APP_DIR`: app path on the VPS, for example `/opt/resys-api`

## VPS Setup

Install Docker and clone the repository once:

```bash
sudo apt update
sudo apt install -y git ca-certificates curl
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker "$USER"
newgrp docker

sudo mkdir -p /opt/resys-api
sudo chown "$USER:$USER" /opt/resys-api
git clone <your-repo-url> /opt/resys-api
cd /opt/resys-api
```

Create the production `.env` file on the VPS:

```bash
cat > .env <<'EOF'
ENVIRONMENT=production
JWT_SECRET_KEY=replace-with-a-long-random-secret-at-least-32-bytes
ADMIN_USERNAME=admin
ADMIN_PASSWORD=replace-with-strong-admin-password
LEARNER_USERNAME=learner
LEARNER_PASSWORD=replace-with-strong-learner-password
SQLITE_PATH=data/db.sqlite3
EOF
```

Generate a secret locally or on the VPS:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
```

First manual deploy:

```bash
docker compose up --build -d
docker compose logs -f api
curl http://127.0.0.1:8000/healthz
```

After that, every push to `develop` runs the workflow and deploys automatically.
