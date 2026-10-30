from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core import audit, passwords, sessions
from core.config import Settings
from core.deps import CurrentOfficer, get_current_officer, get_db, get_settings_dep, repository
from core.errors import (
    AppError,
    ForbiddenError,
    NotFoundError,
    UnauthorizedError,
    ValidationAppError,
)
from core.pagination import Page, PageParams, page_params
from core.ratelimit import RateLimiter
from shared import avatars
from shared.models.officer import Officer
from shared.repositories.officers import OfficerRepository
from shared.schemas import CurrentOfficerOut, OfficerDirectoryOut, OfficerOut, SignInOut

router = APIRouter(prefix="/api/v1/officers", tags=["officers"])

get_repo = repository(OfficerRepository)

#: Ten attempts per client and account per minute: enough for a mistyped password,
#: far too slow to guess one.
SIGNIN_LIMITER = RateLimiter(limit=10, window_seconds=60.0)


class RateLimitedError(AppError):
    status_code = 429
    code = "rate_limited"


class SignInIn(BaseModel):
    officer_id: str = Field(max_length=36)
    password: str = Field(max_length=passwords.MAX_LENGTH)


class PasswordIn(BaseModel):
    current_password: str = Field(max_length=passwords.MAX_LENGTH)
    new_password: str = Field(max_length=passwords.MAX_LENGTH)


class ProfileIn(BaseModel):
    """What a person may change about themselves. The name is administrators only."""

    full_name: str | None = Field(default=None, max_length=120)
    email: str | None = Field(default=None, max_length=254)
    phone: str | None = Field(default=None, max_length=32)


def _own_phone(country: str, raw: str | None) -> str:
    """A required mobile, normalised to the local way of writing it.

    The profile is what an administrator phones when a field officer cannot sign in,
    so a missing or letter-filled number is worth refusing here rather than leaving a
    contact that cannot be dialled.
    """
    compact = re.sub(r"[\s\-()]", "", (raw or "").strip())
    if not compact:
        raise ValidationAppError("A mobile number is required.", code="phone_required")
    if not re.fullmatch(r"\+?\d{1,15}", compact):
        raise ValidationAppError(
            "A phone number can only contain digits, spaces, dashes and a leading +.",
            code="phone_invalid",
        )
    digits = compact.lstrip("+")
    if country == "PK":
        local = (
            digits[4:]
            if digits.startswith("0092")
            else digits[2:]
            if digits.startswith("92") and len(digits) == 12
            else digits[1:]
            if digits.startswith("0")
            else digits
        )
        if len(local) != 10 or not local.startswith("3"):
            raise ValidationAppError(
                "Enter a Pakistani mobile number, for example 0300-1234567.",
                code="phone_invalid",
            )
        return f"0{local[:3]}-{local[3:]}"
    if country == "GB":
        local = (
            digits[4:]
            if digits.startswith("0044")
            else digits[2:]
            if digits.startswith("44") and len(digits) == 12
            else digits[1:]
            if digits.startswith("0")
            else digits
        )
        if len(local) != 10 or not local.startswith("7"):
            raise ValidationAppError(
                "Enter a UK mobile number, for example 07700 900123.",
                code="phone_invalid",
            )
        return f"0{local[:4]} {local[4:]}"
    if not 7 <= len(digits) <= 15:
        raise ValidationAppError(
            "Enter a phone number of 7 to 15 digits.", code="phone_invalid"
        )
    return compact


def _out(officer: Officer) -> CurrentOfficerOut:
    return CurrentOfficerOut(
        id=officer.id,
        code=officer.code,
        full_name=officer.full_name,
        role=officer.role,
        country=officer.country,
        field_office_id=officer.field_office_id,
        field_office_name=officer.field_office.name if officer.field_office else None,
        email=officer.email,
        phone=officer.phone,
        has_photo=bool(officer.photo_path),
        is_admin=officer.is_admin,
        sees_all=officer.sees_all,
    )


def _row(session: Session, officer: CurrentOfficer) -> Officer:
    row = OfficerRepository(session).get_with_office(officer.id)
    if row is None:  # pragma: no cover - the dependency already resolved this officer
        raise NotFoundError("Officer not found.", code="officer_not_found_by_id")
    return row


def _may_hold_photo(role: str) -> bool:
    """All officers, staff and administrators may set a profile photo."""
    return bool(role)


@router.get("", response_model=Page[OfficerOut], summary="List officers")
def list_officers(
    params: PageParams = Depends(page_params),
    country: str | None = Query(None, min_length=2, max_length=2),
    field_office_id: str | None = Query(None),
    role: Literal["officer", "staff", "admin"] | None = Query(None),
    q: str | None = Query(None, max_length=120),
    repo: OfficerRepository = Depends(get_repo),
    officer: CurrentOfficer = Depends(get_current_officer),
) -> Page[OfficerOut]:
    del officer  # any signed-in officer may read the directory; contact details included
    result = repo.search(params, country=country, field_office_id=field_office_id, role=role, q=q)
    return Page[OfficerOut](
        items=[OfficerOut.model_validate(o) for o in result.rows],
        total=result.total,
        page=params.page,
        page_size=params.page_size,
    )


@router.get(
    "/directory",
    response_model=Page[OfficerDirectoryOut],
    summary="Accounts for the sign-in screen (public, no contact details)",
)
def officer_directory(
    params: PageParams = Depends(page_params),
    country: str | None = Query(None, min_length=2, max_length=2),
    role: Literal["officer", "staff", "admin"] | None = Query(None),
    q: str | None = Query(None, max_length=120),
    repo: OfficerRepository = Depends(get_repo),
) -> Page[OfficerDirectoryOut]:
    """The sign-in screen must list accounts before anyone has signed in, so this route
    is public. It exposes only what the picker shows: name, role, country and office."""
    result = repo.search(params, country=country, field_office_id=None, role=role, q=q)
    return Page[OfficerDirectoryOut](
        items=[OfficerDirectoryOut.model_validate(o) for o in result.rows],
        total=result.total,
        page=params.page,
        page_size=params.page_size,
    )


@router.post("/sign-in", response_model=SignInOut, summary="Sign in with a password")
def sign_in(
    body: SignInIn,
    request: Request,
    session: Session = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
) -> SignInOut:
    """Check the password and mint a token for later requests.

    The token goes in ``Authorization: Bearer ...``. The ``X-Officer-Id`` header is not
    a security boundary and is ignored in production. Attempts are rate limited so a
    known default password cannot be guessed in bulk.
    """
    client = request.client.host if request.client else "unknown"
    officer_id = body.officer_id.strip()
    allowed, retry_after = SIGNIN_LIMITER.check(f"{client}:{officer_id}")
    if not allowed:
        raise RateLimitedError(
            "Too many sign-in attempts. Try again shortly.",
            details={"retry_after_seconds": retry_after},
        )

    repo = OfficerRepository(session)
    officer = repo.get_with_office(officer_id)
    if officer is None or not passwords.verify_password(body.password, officer.password_hash):
        raise UnauthorizedError(
            "That password does not match this account.", code="invalid_credentials"
        )
    if not officer.active:
        raise ForbiddenError("This officer is inactive.", code="officer_inactive")
    token = sessions.issue(settings, officer.id)
    return SignInOut(
        token=token,
        expires_at=datetime.now(UTC)
        + timedelta(seconds=settings.session_ttl_seconds),
        officer=_out(officer),
    )


@router.get("/me", response_model=CurrentOfficerOut, summary="The acting officer")
def me(
    officer: CurrentOfficer = Depends(get_current_officer), session: Session = Depends(get_db)
) -> CurrentOfficerOut:
    return _out(_row(session, officer))


@router.put("/me", response_model=CurrentOfficerOut, summary="Change my own details")
def update_me(
    body: ProfileIn,
    officer: CurrentOfficer = Depends(get_current_officer),
    session: Session = Depends(get_db),
) -> CurrentOfficerOut:
    row = _row(session, officer)
    before = {"full_name": row.full_name, "email": row.email, "phone": row.phone}

    if body.full_name is not None and body.full_name.strip() != row.full_name:
        if not officer.is_admin:
            raise ForbiddenError(
                "Only an administrator can change a name. Ask one to change it for you.",
                code="name_admin_only",
            )
        name = body.full_name.strip()
        if not name:
            raise ValidationAppError("A name cannot be empty.", code="name_required")
        row.full_name = name
    if body.email is not None:
        row.email = body.email.strip() or None
    # Every save carries the mobile: it is the only contact an administrator has when
    # this officer is locked out, so a profile without one is not worth keeping.
    row.phone = _own_phone(row.country, body.phone if body.phone is not None else row.phone)

    row.updated_by = officer.id
    session.flush()
    diff = audit.compute_diff(
        before, {"full_name": row.full_name, "email": row.email, "phone": row.phone}
    )
    if diff:
        audit.record("officer", row.id, audit.ACTION_UPDATE, officer.id, diff, session=session)
    session.commit()
    return _out(row)


@router.post("/me/password", response_model=CurrentOfficerOut, summary="Change my password")
def change_password(
    body: PasswordIn,
    officer: CurrentOfficer = Depends(get_current_officer),
    session: Session = Depends(get_db),
) -> CurrentOfficerOut:
    row = _row(session, officer)
    if not passwords.verify_password(body.current_password, row.password_hash):
        raise UnauthorizedError(
            "The current password is not right.", code="invalid_credentials"
        )
    new = body.new_password.strip()
    if len(new) < passwords.MIN_LENGTH:
        raise ValidationAppError(
            f"A password needs at least {passwords.MIN_LENGTH} characters.",
            code="password_too_short",
        )
    row.password_hash = passwords.hash_password(new)
    row.updated_by = officer.id
    session.flush()
    # The hash itself is never written to the log, only that it changed.
    audit.record(
        "officer",
        row.id,
        audit.ACTION_UPDATE,
        officer.id,
        {"password": {"from": None, "to": "changed"}},
        session=session,
    )
    session.commit()
    return _out(row)


@router.post("/me/photo", response_model=CurrentOfficerOut, summary="Set my profile photo")
async def set_photo(
    request: Request,
    file: UploadFile = File(...),
    officer: CurrentOfficer = Depends(get_current_officer),
    session: Session = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
) -> CurrentOfficerOut:
    if not _may_hold_photo(officer.role):
        raise ForbiddenError(
            "A field officer account does not carry a photo.", code="photo_not_allowed"
        )
    content = await file.read()
    row = _row(session, officer)
    previous = row.photo_path
    row.photo_path = avatars.store_avatar(settings.upload_path, row.id, content)
    row.updated_by = officer.id
    session.flush()
    audit.record(
        "officer",
        row.id,
        audit.ACTION_UPDATE,
        officer.id,
        {"photo": {"from": "set" if previous else None, "to": "set"}},
        session=session,
    )
    session.commit()
    avatars.remove_avatar(settings.upload_path, previous)
    _ = request  # the body is read above; FastAPI needs the request for the upload
    return _out(row)


@router.delete("/me/photo", response_model=CurrentOfficerOut, summary="Remove my profile photo")
def delete_photo(
    officer: CurrentOfficer = Depends(get_current_officer),
    session: Session = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
) -> CurrentOfficerOut:
    row = _row(session, officer)
    previous = row.photo_path
    row.photo_path = None
    row.updated_by = officer.id
    session.flush()
    if previous:
        audit.record(
            "officer",
            row.id,
            audit.ACTION_UPDATE,
            officer.id,
            {"photo": {"from": "set", "to": None}},
            session=session,
        )
    session.commit()
    avatars.remove_avatar(settings.upload_path, previous)
    return _out(row)


@router.get("/{officer_id}/photo", response_class=FileResponse, summary="An officer's photo")
def get_photo(
    officer_id: str,
    session: Session = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
) -> FileResponse:
    row = OfficerRepository(session).get(officer_id)
    path = avatars.avatar_file(settings.upload_path, row.photo_path if row else None)
    if path is None:
        raise NotFoundError("This officer has no photo.", code="photo_not_found")
    return FileResponse(
        path, media_type=avatars.MIME, headers={"Cache-Control": "no-cache"}
    )


@router.get("/{officer_id}", response_model=OfficerOut, summary="One officer")
def get_officer(
    officer_id: str,
    repo: OfficerRepository = Depends(get_repo),
    officer: CurrentOfficer = Depends(get_current_officer),
) -> OfficerOut:
    del officer  # contact details are for signed-in staff only
    row = repo.get_with_office(officer_id)
    if row is None:
        raise NotFoundError("Officer not found.", code="officer_not_found_by_id")
    return OfficerOut.model_validate(row)
