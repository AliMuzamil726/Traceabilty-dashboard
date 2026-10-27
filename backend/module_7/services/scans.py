"""Scan logging. Never stores a raw address; never blocks or fails the response."""

from __future__ import annotations

import hashlib
import logging
import re

from sqlalchemy.orm import Session

from core import events
from core.database import Database, utcnow
from core.events import bus
from core.ratelimit import RateLimiter
from module_7.models import QrScanLog

logger = logging.getLogger("sawie.module_7")

#: Public lookups per address per minute: plenty for people scanning labels, far too few
#: to walk a 2**60 token space.
public_limiter = RateLimiter(limit=30, window_seconds=60.0)


def ip_hash(ip: str | None, salt: str) -> str | None:
    if not ip:
        return None
    return hashlib.sha256(f"{salt}:{ip}".encode()).hexdigest()


def user_agent_family(ua: str | None) -> str:
    text = ua or ""
    mobile = bool(re.search(r"Mobile|Android|iPhone|iPad", text))
    if "Edg/" in text:
        name = "Edge"
    elif "Firefox/" in text:
        name = "Firefox"
    elif "Chrome/" in text or "CriOS/" in text:
        name = "Chrome"
    elif "Safari/" in text:
        name = "Safari"
    elif text:
        name = "Other"
    else:
        return "Unknown"
    return f"{name} mobile" if mobile else name


def record_scan(
    database: Database,
    token_id: str,
    *,
    channel: str,
    ip: str | None,
    ua: str | None,
    salt: str,
    token_type: str,
    heap_id: str,
    bale_serial: str | None,
) -> None:
    """Run after the response is sent, in its own session. Every failure is swallowed."""
    try:
        with database.session_scope() as session:
            _write(
                session,
                token_id,
                channel=channel,
                ip=ip,
                ua=ua,
                salt=salt,
                token_type=token_type,
                heap_id=heap_id,
                bale_serial=bale_serial,
            )
    except Exception:  # noqa: BLE001 - logging a scan must never fail a served response
        logger.warning("Could not record a QR scan", exc_info=True)


def _write(
    session: Session,
    token_id: str,
    *,
    channel: str,
    ip: str | None,
    ua: str | None,
    salt: str,
    token_type: str,
    heap_id: str,
    bale_serial: str | None,
) -> None:
    row = QrScanLog(
        token_id=token_id,
        scanned_at=utcnow(),
        channel=channel,
        ip_hash=ip_hash(ip, salt),
        user_agent_family=user_agent_family(ua),
    )
    session.add(row)
    session.flush()
    bus.publish(
        events.QR_SCANNED,
        {
            "qr_token_id": token_id,
            "token_type": token_type,
            "heap_id": heap_id,
            "bale_serial": bale_serial,
            "channel": channel,
            "scanned_at": row.scanned_at.isoformat(),
        },
        session=session,
    )
