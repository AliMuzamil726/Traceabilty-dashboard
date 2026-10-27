"""Shared pytest fixtures. Every test runs against its own temporary SQLite file."""

from __future__ import annotations

import os
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest

# Isolate tests from the developer database before any app module is imported.
_SESSION_TMP = Path(tempfile.mkdtemp(prefix="sawie-tests-"))
os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = f"sqlite:///{(_SESSION_TMP / 'import.db').as_posix()}"
os.environ["UPLOAD_DIR"] = str(_SESSION_TMP / "storage")
os.environ["SEED_ON_START"] = "true"

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.main import create_app  # noqa: E402
from app.registry import import_all_models  # noqa: E402
from core.config import Settings  # noqa: E402
from core.database import Database  # noqa: E402


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        app_env="test",
        database_url=f"sqlite:///{(tmp_path / 'test.db').as_posix()}",
        upload_dir=str(tmp_path / "storage"),
        seed_on_start=True,
        _env_file=None,  # type: ignore[call-arg]
    )


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    app = create_app(settings)
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def database(settings: Settings) -> Iterator[Database]:
    import_all_models()
    db = Database(settings.resolved_database_url)
    db.create_all()
    yield db
    db.dispose()


@pytest.fixture
def session(database: Database) -> Iterator[Session]:
    s = database.session_factory()
    try:
        yield s
    finally:
        s.rollback()
        s.close()
