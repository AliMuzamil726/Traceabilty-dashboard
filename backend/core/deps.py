"""FastAPI dependencies: settings, database session and the current officer.

Transaction rule: :func:`get_db` never commits. Service methods that write call
``session.commit()`` themselves, so a commit failure always surfaces as an error
response. Anything left uncommitted is rolled back when the session closes.

Officer context: sign-in mints a signed token (``core.sessions``) that the client sends
as ``Authorization: Bearer ...``. In development and tests the ``X-Officer-Id`` header
still selects the acting officer, so the officer switcher and every test keep working;
in production the header is ignored and only a token counts.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Any, TypeVar

from fastapi import Depends, Header, Request
from sqlalchemy.orm import Session

from core import sessions
from core.config import Settings
from core.database import Database
from core.errors import ForbiddenError, UnauthorizedError
from shared.models.officer import ROLE_ADMIN, SEES_ALL_ROLES, Officer
from shared.repositories.officers import OfficerRepository

OFFICER_HEADER = "X-Officer-Id"

RepoT = TypeVar("RepoT")


def get_settings_dep(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def get_database(request: Request) -> Database:
    database: Database = request.app.state.db
    return database


def get_db(request: Request, database: Database = Depends(get_database)) -> Iterator[Session]:
    """A session for this request: read-only for GET/HEAD, write-capable otherwise."""
    if request.method in ("GET", "HEAD"):
        factory = database.read_session_factory
    else:
        factory = database.session_factory
    session = factory()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_write_db(
    request: Request, database: Database = Depends(get_database)
) -> Iterator[Session]:
    """A write-capable session for the few GET routes that record something."""
    del request
    session = database.session_factory()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def repository(cls: Callable[[Session], RepoT]) -> Callable[..., RepoT]:
    """Build a dependency that returns ``cls(session)``."""

    def _dependency(session: Session = Depends(get_db)) -> RepoT:
        return cls(session)

    _dependency.__name__ = f"get_{getattr(cls, '__name__', 'repository')}"
    return _dependency


@dataclass(frozen=True)
class CurrentOfficer:
    """Plain snapshot of the acting officer (safe to pass between modules)."""

    id: str
    code: str
    full_name: str
    role: str
    country: str
    field_office_id: str | None
    field_office_name: str | None

    @property
    def is_admin(self) -> bool:
        return self.role == ROLE_ADMIN

    @property
    def sees_all(self) -> bool:
        """Administrator or staff: works on every officer's farmers and records."""
        return self.role in SEES_ALL_ROLES

    @classmethod
    def from_model(cls, officer: Officer) -> CurrentOfficer:
        return cls(
            id=officer.id,
            code=officer.code,
            full_name=officer.full_name,
            role=officer.role,
            country=officer.country,
            field_office_id=officer.field_office_id,
            field_office_name=officer.field_office.name if officer.field_office else None,
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "code": self.code,
            "full_name": self.full_name,
            "role": self.role,
            "country": self.country,
            "field_office_id": self.field_office_id,
            "field_office_name": self.field_office_name,
        }


def get_current_officer(
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_officer_id: str | None = Header(default=None, alias=OFFICER_HEADER),
    session: Session = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
) -> CurrentOfficer:
    bearer = sessions.bearer_token(authorization)
    token_officer_id = sessions.verify(settings, bearer) if bearer else None
    if bearer and token_officer_id is None:
        raise UnauthorizedError(
            "Your session is no longer valid. Sign in again.", code="session_invalid"
        )

    header_id = (x_officer_id or "").strip()
    if header_id and settings.is_dev:
        officer_id = header_id
    elif token_officer_id:
        officer_id = token_officer_id
    elif settings.is_dev:
        officer = OfficerRepository(session).get_by_code(settings.default_officer_code)
        if officer is None:
            raise UnauthorizedError(
                "No officer selected and the default development officer is missing. "
                "Run the seed script.",
                code="officer_required",
            )
        if not officer.active:
            raise ForbiddenError("This officer is inactive.", code="officer_inactive")
        return CurrentOfficer.from_model(officer)
    else:
        raise UnauthorizedError("Sign in to continue.", code="officer_required")

    officer = OfficerRepository(session).get_with_office(officer_id)
    if officer is None:
        raise UnauthorizedError(
            "The selected officer does not exist.",
            code="officer_not_found",
            details={"officer_id": officer_id},
        )
    if not officer.active:
        raise ForbiddenError("This officer is inactive.", code="officer_inactive")
    return CurrentOfficer.from_model(officer)


def require_admin(officer: CurrentOfficer = Depends(get_current_officer)) -> CurrentOfficer:
    if not officer.is_admin:
        raise ForbiddenError("Administrator role required.", code="admin_required")
    return officer
