from __future__ import annotations

import logging
import os
import secrets
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

_INSECURE_DEFAULTS = frozenset({"replace-with-secure-key", ""})

log = logging.getLogger(__name__)


def _generate_credentials() -> tuple[str, str, str, str]:
    admin_user = os.getenv("ADMIN_USERNAME", "admin")
    admin_pass = os.getenv("ADMIN_PASSWORD", "")
    learner_user = os.getenv("LEARNER_USERNAME", "learner")
    learner_pass = os.getenv("LEARNER_PASSWORD", "")
    return admin_user, admin_pass, learner_user, learner_pass


@dataclass
class Settings:
    app_name: str = os.getenv("APP_NAME", "MARS Recommender API")
    api_prefix: str = os.getenv("API_PREFIX", "/api/v1")
    artifact_root: Path = Path(
        os.getenv("ARTIFACT_ROOT", "artifacts/recommender/current")
    )
    model_checkpoint_path: Path = Path(
        os.getenv("MODEL_CHECKPOINT_PATH", "models/checkpoints/bert4rec.pt")
    )
    text_embeddings_path: Path = Path(
        os.getenv("TEXT_EMBEDDINGS_PATH", "models/sentence-camembert-base.pt")
    )
    environment: str = os.getenv("ENVIRONMENT", "development")
    jwt_secret_key: str = os.getenv("JWT_SECRET_KEY", "")
    jwt_algorithm: str = os.getenv("JWT_ALGORITHM", "HS256")
    access_token_expire_minutes: int = int(
        os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60")
    )
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    database_url: str = os.getenv(
        "DATABASE_URL", "postgresql://user:password@localhost:5432/mars"
    )
    admin_username: str = ""
    admin_password: str = ""
    learner_username: str = ""
    learner_password: str = ""

    def validate(self) -> None:
        if self.environment == "production":
            if not self.jwt_secret_key or self.jwt_secret_key in _INSECURE_DEFAULTS:
                raise ValueError(
                    "JWT_SECRET_KEY environment variable must be set to a secure "
                    "random value in production. Generate one with: "
                    'python -c "import secrets; print(secrets.token_urlsafe(48))"'
                )

            admin_user, admin_pass, learner_user, learner_pass = _generate_credentials()
            if not admin_pass:
                raise ValueError(
                    "ADMIN_PASSWORD environment variable must be set in production. "
                    "Generate one with: "
                    'python -c "import secrets; print(secrets.token_urlsafe(16))"'
                )
            if not learner_pass:
                raise ValueError(
                    "LEARNER_PASSWORD environment variable must be set in production. "
                    "Generate one with: "
                    'python -c "import secrets; print(secrets.token_urlsafe(16))"'
                )
            self.admin_username = admin_user
            self.admin_password = admin_pass
            self.learner_username = learner_user
            self.learner_password = learner_pass
        else:
            if not self.jwt_secret_key or self.jwt_secret_key in _INSECURE_DEFAULTS:
                self.jwt_secret_key = secrets.token_urlsafe(48)

            admin_user, admin_pass, learner_user, learner_pass = _generate_credentials()
            self.admin_username = admin_user
            self.learner_username = learner_user

            if not admin_pass:
                self.admin_password = secrets.token_urlsafe(16)
                log.warning(
                    "ADMIN_PASSWORD not set — generated random: %s",
                    self.admin_password,
                )
            else:
                self.admin_password = admin_pass

            if not learner_pass:
                self.learner_password = secrets.token_urlsafe(16)
                log.warning(
                    "LEARNER_PASSWORD not set — generated random: %s",
                    self.learner_password,
                )
            else:
                self.learner_password = learner_pass


settings = Settings()
settings.validate()
