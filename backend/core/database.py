"""Database engine, session factory and portable column types.

Rules that keep the project ready for Supabase (Postgres):
* only portable SQLAlchemy types are used (no SQLite-only features, no PostGIS);
* every timestamp is stored in UTC through :class:`UTCDateTime`;
* primary keys are strings (UUIDs) and never assumed to be integers;
* switching databases means changing ``DATABASE_URL`` and nothing else.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime, MetaData, String, create_engine, event, text
from sqlalchemy.engine import Dialect, Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker
from sqlalchemy.pool import NullPool
from sqlalchemy.types import TypeDecorator

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


def utcnow() -> datetime:
    """Timezone-aware current UTC time."""
    return datetime.now(UTC)


def new_uuid() -> str:
    """Random string primary key."""
    return str(uuid.uuid4())


class UTCDateTime(TypeDecorator[datetime]):
    """DateTime that always stores UTC and always returns timezone-aware UTC values."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("Naive datetimes are not allowed; use timezone-aware UTC values.")
        return value.astimezone(UTC)

    def process_result_value(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)


class Base(DeclarativeBase):
    """Declarative base for every table in the product."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class IdMixin:
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), default=utcnow, onupdate=utcnow, nullable=False
    )


class ActorMixin:
    """Who created and last changed a row (officer ids)."""

    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    updated_by: Mapped[str | None] = mapped_column(String(36), nullable=True)


def _configure_sqlite(engine: Engine, *, immediate_writes: bool) -> None:
    """Make pysqlite transactions explicit and race-safe.

    pysqlite's own transaction handling is disabled and every transaction is opened
    explicitly. Write engines use ``BEGIN IMMEDIATE`` so the write lock is taken up
    front, which makes the ID counters race-free without SQLite-specific code in the
    repositories. Read engines use a plain (deferred) ``BEGIN``: in WAL mode readers do
    not block the writer nor each other, so a page load no longer waits behind an
    unrelated write.
    """

    @event.listens_for(engine, "connect")
    def _on_connect(dbapi_connection: Any, _record: Any) -> None:
        dbapi_connection.isolation_level = None
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.close()

    begin_sql = "BEGIN IMMEDIATE" if immediate_writes else "BEGIN"

    @event.listens_for(engine, "begin")
    def _on_begin(conn: Any) -> None:
        conn.exec_driver_sql(begin_sql)


def make_engine(url: str, *, immediate_writes: bool = True, pooled: bool = True) -> Engine:
    """Create an engine for ``url`` with dialect-appropriate settings."""
    if url.startswith("sqlite"):
        engine = create_engine(
            url,
            connect_args={"check_same_thread": False, "timeout": 30},
            future=True,
            **({} if pooled else {"poolclass": NullPool}),
        )
        _configure_sqlite(engine, immediate_writes=immediate_writes)
        return engine
    return create_engine(url, pool_pre_ping=True, future=True)


class Database:
    """Owns the engines and session factories.

    ``session_factory`` is for work that may write (``BEGIN IMMEDIATE`` on SQLite).
    ``read_session_factory`` is for read-only requests: it never takes the write lock,
    so concurrent reads do not queue behind a write. Endpoints that only read use it
    through :func:`core.deps.get_db`; the few GET routes that write ask for
    :func:`core.deps.get_write_db` explicitly.
    """

    def __init__(self, url: str) -> None:
        self.url = url
        self.engine = make_engine(url)
        self.session_factory = sessionmaker(
            bind=self.engine, autoflush=False, expire_on_commit=False, class_=Session
        )
        in_memory = url.startswith("sqlite") and ":memory:" in url
        if url.startswith("sqlite") and not in_memory:
            # NullPool: a finished read request closes its connection, so no idle
            # handle keeps the WAL file open (Windows blocks the backup-restore swap
            # otherwise).
            self.read_engine = make_engine(url, immediate_writes=False, pooled=False)
            self.read_session_factory = sessionmaker(
                bind=self.read_engine, autoflush=False, expire_on_commit=False, class_=Session
            )
        else:
            # Postgres has row-level locking, and an in-memory database only exists
            # inside one engine, so both share the write factory.
            self.read_engine = self.engine
            self.read_session_factory = self.session_factory

    @property
    def dialect(self) -> str:
        return self.engine.dialect.name

    def create_all(self) -> None:
        Base.metadata.create_all(self.engine)

    def drop_all(self) -> None:
        Base.metadata.drop_all(self.engine)

    def is_reachable(self) -> bool:
        try:
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except Exception:  # noqa: BLE001 - health check must never raise
            return False

    @contextmanager
    def session_scope(self) -> Iterator[Session]:
        """Unit of work: commit on success, roll back on any exception."""
        session = self.session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def dispose(self) -> None:
        if self.read_engine is not self.engine:
            self.read_engine.dispose()
        self.engine.dispose()


_PROCESS_DATABASE: Database | None = None


def set_process_database(database: Database | None) -> None:
    """Remember the app's database so helpers without a request session can read it.

    Used by :mod:`core.app_settings`, which resolves a setting for callers that hold
    no session (a background helper, a formatter). The composition root sets it when
    the app starts and clears it on shutdown.
    """
    global _PROCESS_DATABASE
    _PROCESS_DATABASE = database


def get_process_database() -> Database | None:
    return _PROCESS_DATABASE
