"""Public API of Module 7 (QR Tracing).

The ONLY file other modules may import from this module.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from core.config import get_settings
from module_6 import public_api as heaps
from module_7.models import ACTIVE
from module_7.repository import ScanRepository, TokenRepository
from module_7.services import trace
from module_7.services.qr import QrService
from module_7.services.tokens import looks_like_token


@dataclass(frozen=True)
class QrTokenDTO:
    token: str
    token_type: str
    bale_serial: str | None
    heap_id: str
    status: str
    trace_url: str
    label_print_count: int
    created_at: datetime


@dataclass(frozen=True)
class ScanSummaryDTO:
    total: int
    public: int
    internal: int
    last_scan_at: datetime | None


@dataclass(frozen=True)
class TokenQuery:
    heap_id: str | None = None
    token_type: str | None = None


@dataclass(frozen=True)
class ScanTotalsDTO:
    """Scans and live codes for a crop programme and time range. Added for Module 1.

    A scan is not tagged with a crop; it belongs to a code, and a code belongs to a
    heap or batch, which has one. So a crop filter resolves that crop's heaps first
    (D-096).
    """

    total: int
    public: int
    internal: int
    last_scan_at: datetime | None
    active_tokens: int


def get_scan_totals(
    session: Session,
    *,
    crop: str | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
) -> ScanTotalsDTO:
    """Scan counts and live codes, optionally for one crop and time range."""
    tokens = TokenRepository(session)
    heap_ids: list[str] | None = None
    if crop:
        heap_ids = heaps.list_heap_ids(session, crop=crop)
    total, public, last = ScanRepository(session).totals(
        heap_ids=heap_ids, since=since, until=until
    )
    return ScanTotalsDTO(
        total=total,
        public=public,
        internal=total - public,
        last_scan_at=last,
        active_tokens=tokens.count_active(heap_ids=heap_ids),
    )


def get_token_for_bale(session: Session, serial: str) -> QrTokenDTO | None:
    row = TokenRepository(session).active_for_bale(serial)
    if row is None:
        return None
    url = QrService(session, get_settings()).url(row.token)
    return QrTokenDTO(
        row.token,
        row.token_type,
        row.bale_serial,
        row.heap_id,
        row.status,
        url,
        row.label_print_count,
        row.created_at,
    )


def get_trace_for_token(
    session: Session, token: str, *, public: bool = True
) -> dict[str, Any] | None:
    """The public payload (default) or, with ``public=False``, the full internal chain."""
    if public:
        found = QrService(session, get_settings()).public_trace(token)
        return found[0] if found else None
    row = (
        TokenRepository(session).by_token(token.upper())
        if looks_like_token(token.upper())
        else None
    )
    if row is None or row.status != ACTIVE:
        return None
    f = trace.facts(session, row.heap_id, with_geometry=True)
    if f is None:
        return None
    bale = heaps.get_bale(session, row.bale_serial) if row.bale_serial else None
    return trace.internal_trace(session, f, bale, officer_id="system")


def get_scan_summary(session: Session, query: TokenQuery | None = None) -> ScanSummaryDTO:
    q = query or TokenQuery()
    ids = None
    if q.heap_id:
        repo = TokenRepository(session)
        ids = [t.id for t in repo.for_heap_bales(q.heap_id)]
        heap_token = repo.active_for_heap(q.heap_id)
        if heap_token:
            ids.append(heap_token.id)
    total, public, last = ScanRepository(session).summary(ids)
    return ScanSummaryDTO(total, public, total - public, last)


def count_active_tokens(session: Session, query: TokenQuery | None = None) -> int:
    q = query or TokenQuery()
    return TokenRepository(session).count_active(
        token_type=q.token_type, heap_ids=[q.heap_id] if q.heap_id else None
    )


__all__ = [
    "QrTokenDTO",
    "ScanSummaryDTO",
    "ScanTotalsDTO",
    "TokenQuery",
    "count_active_tokens",
    "get_scan_summary",
    "get_scan_totals",
    "get_token_for_bale",
    "get_trace_for_token",
]
