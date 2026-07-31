# Use the official ghcr.io/astral-sh/uv image with python 3.12 pre-installed
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

WORKDIR /app

# Enable bytecode compilation to make imports faster
ENV UV_COMPILE_BYTECODE=1

# Copy dependency configs
COPY pyproject.toml uv.lock ./

# Install dependencies using cache mount for faster builds
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

# Final slim stage
FROM python:3.12-slim-bookworm

WORKDIR /app

# Copy the virtual environment from the builder stage
COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

# Copy application files
COPY . .
RUN chmod +x /app/scripts/docker-entrypoint.sh

# Expose port 8000 for FastAPI
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=3).read()" || exit 1

# Start uvicorn server
ENTRYPOINT ["/app/scripts/docker-entrypoint.sh"]
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
