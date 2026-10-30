"""Signed, stateless session tokens.

Sign-in mints a token that names the officer and an expiry; every later request may
send it as ``Authorization: Bearer <token>``. The token is signed with HMAC-SHA256 so
the server can trust the officer id inside it without a session table.

The signing key comes from ``SESSION_SECRET`` when set, otherwise from the deployment's
``QR_IP_SALT`` (already guarded to be long and deployment-specific in production). The
token is not encrypted: it carries nothing but the officer id and timestamps.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Final

from core.config import Settings

_TOKEN_CONTEXT: Final = b"sawie.session.v1"


def _signing_key(settings: Settings) -> bytes:
    secret = settings.session_secret or settings.qr_ip_salt
    return hmac.new(secret.encode("utf-8"), _TOKEN_CONTEXT, hashlib.sha256).digest()


def _encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _decode(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def issue(settings: Settings, officer_id: str, *, now: float | None = None) -> str:
    """Mint a token for ``officer_id`` valid for ``settings.session_ttl_seconds``."""
    issued = int(time.time() if now is None else now)
    payload = {"sub": officer_id, "iat": issued, "exp": issued + settings.session_ttl_seconds}
    body = _encode(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    signature = hmac.new(_signing_key(settings), body.encode("ascii"), hashlib.sha256).digest()
    return f"{body}.{_encode(signature)}"


def bearer_token(authorization: str | None) -> str | None:
    """The token part of an ``Authorization: Bearer ...`` header, if present."""
    if not authorization:
        return None
    scheme, _, value = authorization.partition(" ")
    if scheme.lower() != "bearer" or not value.strip():
        return None
    return value.strip()


def verify(settings: Settings, token: str, *, now: float | None = None) -> str | None:
    """The officer id a valid, unexpired token names; ``None`` otherwise."""
    body, separator, signature = token.partition(".")
    if not separator or not body or not signature:
        return None
    try:
        expected = hmac.new(_signing_key(settings), body.encode("ascii"), hashlib.sha256).digest()
        provided = _decode(signature)
    except ValueError:
        return None
    if not hmac.compare_digest(expected, provided):
        return None
    try:
        payload = json.loads(_decode(body))
    except ValueError:
        return None
    if not isinstance(payload, dict):
        return None
    subject = payload.get("sub")
    expires = payload.get("exp")
    if not isinstance(subject, str) or not subject:
        return None
    if not isinstance(expires, int | float) or isinstance(expires, bool):
        return None
    if expires <= (time.time() if now is None else now):
        return None
    return subject


__all__ = ["bearer_token", "issue", "verify"]
