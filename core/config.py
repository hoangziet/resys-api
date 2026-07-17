from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os


@dataclass
class Settings:
    app_name: str = os.getenv("APP_NAME", "MARS Recommender API")
    api_prefix: str = os.getenv("API_PREFIX", "/api/v1")
    artifact_root: Path = Path(os.getenv("ARTIFACT_ROOT", "artifacts/recommender/current"))
    model_checkpoint_path: Path = Path(os.getenv("MODEL_CHECKPOINT_PATH", "models/checkpoints/checkpoint.pt"))
    environment: str = os.getenv("ENVIRONMENT", "development")
    jwt_secret_key: str = os.getenv("JWT_SECRET_KEY", "replace-with-secure-key")
    jwt_algorithm: str = os.getenv("JWT_ALGORITHM", "HS256")
    access_token_expire_minutes: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    database_url: str = os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/mars")


settings = Settings()
