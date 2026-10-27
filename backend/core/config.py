"""Application settings loaded from environment variables and ``backend/.env``.

Only ``DATABASE_URL`` decides which database is used. Relative SQLite paths and the
upload directory are resolved against the ``backend/`` folder so the app behaves the
same no matter which directory it is started from.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR: Path = Path(__file__).resolve().parents[1]
APP_VERSION = "0.1.0"

_SQLITE_PREFIX = "sqlite:///"


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
    seed_on_start: bool = True
    default_officer_code: str = Field(
        default="PK-MUL-01",
        description="Officer used in development when no X-Officer-Id header is sent.",
    )
    log_level: str = "INFO"

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
