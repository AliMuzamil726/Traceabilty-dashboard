"""Application settings loaded from environment variables and ``backend/.env``.

Only ``DATABASE_URL`` decides which database is used. Relative SQLite paths and the
upload directory are resolved against the ``backend/`` folder so the app behaves the
same no matter which directory it is started from.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR: Path = Path(__file__).resolve().parents[1]
APP_VERSION = "0.1.0"

_SQLITE_PREFIX = "sqlite:///"

#: Placeholder salts shipped in the repo. They are fine for development, never for a
#: real deployment: the QR scan log would hash every scanner address the same way.
INSECURE_QR_IP_SALTS = frozenset(
    {"sawie-dev-salt-change-me", "change-me-to-a-long-random-string"}
)


class Settings(BaseSettings):
    """Typed runtime configuration."""

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "SAWIE"
    app_version: str = APP_VERSION
    app_env: Literal["development", "test", "production"] = "development"
    database_url: str = Field(default="sqlite:///./data/sawie.db")
    cors_origins: str = Field(default="http://localhost:5173,http://127.0.0.1:5173")
    public_base_url: str = Field(default="http://localhost:5173")
    #: Salt for hashing scanner IP addresses (QR scan log). Change it per deployment.
    qr_ip_salt: str = Field(default="sawie-dev-salt-change-me")
    upload_dir: str = Field(default="./storage")
    seed_on_start: bool = False
    default_officer_code: str = Field(
        default="PK-MUL-01",
        description="Officer used in development when no X-Officer-Id header is sent.",
    )
    log_level: str = "INFO"

    @model_validator(mode="after")
    def _guard_production(self) -> Settings:
        self.check_production()
        return self

    def check_production(self) -> None:
        """Refuse settings that would be unsafe in production.

        Called on construction and again at startup, because ``model_copy`` skips
        validators and is easy to reach for in tests and scripts.
        """
        if self.app_env != "production":
            return
        if self.qr_ip_salt in INSECURE_QR_IP_SALTS or len(self.qr_ip_salt) < 16:
            raise ValueError(
                "QR_IP_SALT must be a deployment-specific value of at least 16 characters "
                "when APP_ENV=production."
            )
        if self.seed_on_start:
            raise ValueError(
                "SEED_ON_START must be false when APP_ENV=production: the demo seed creates "
                "offices and officers with a known default password."
            )

    @property
    def is_dev(self) -> bool:
        return self.app_env in ("development", "test")

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def resolved_database_url(self) -> str:
        """Database URL with relative SQLite paths anchored to ``backend/``."""
        url = self.database_url
        if url.startswith(_SQLITE_PREFIX) and ":memory:" not in url:
            raw = url[len(_SQLITE_PREFIX) :]
            path = Path(raw)
            if not path.is_absolute():
                path = (BACKEND_DIR / path).resolve()
            return f"{_SQLITE_PREFIX}{path.as_posix()}"
        return url

    @property
    def sqlite_path(self) -> Path | None:
        url = self.resolved_database_url
        if url.startswith(_SQLITE_PREFIX) and ":memory:" not in url:
            return Path(url[len(_SQLITE_PREFIX) :])
        return None

    @property
    def upload_path(self) -> Path:
        path = Path(self.upload_dir)
        return path if path.is_absolute() else (BACKEND_DIR / path).resolve()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Process-wide settings instance (cached)."""
    return Settings()
