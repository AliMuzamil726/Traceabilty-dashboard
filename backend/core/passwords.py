"""Password hashing for officer sign-in.

Not a security boundary yet: sign-in checks a password, but every request after it
still carries the acting officer in the ``X-Officer-Id`` header, which anyone can
change (``docs/KNOWN_LIMITATIONS.md``). What this module does buy is that a password
is never stored in readable form, so the dummy accounts can be given real passwords
now and a session layer can be added later without touching the stored rows.

PBKDF2-HMAC-SHA256 with a per-password salt; the stored form carries the algorithm and
the iteration count, so the cost can be raised later without invalidating old hashes.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets

ALGORITHM = "pbkdf2_sha256"
ITERATIONS = 120_000
SALT_BYTES = 16

#: Every seeded account starts here, and the person changes it on their profile screen.
DEFAULT_PASSWORD = "12345678"
MIN_LENGTH = 8
MAX_LENGTH = 128


def hash_password(password: str, *, iterations: int = ITERATIONS) -> str:
    salt = secrets.token_hex(SALT_BYTES)
    digest = _digest(password, salt, iterations)
    return f"{ALGORITHM}${iterations}${salt}${digest}"


def verify_password(password: str, stored: str | None) -> bool:
    """True when the password matches. A missing or unreadable hash never matches."""
    if not stored:
        return False
    try:
        algorithm, raw_iterations, salt, digest = stored.split("$", 3)
        iterations = int(raw_iterations)
    except (ValueError, AttributeError):
        return False
    if algorithm != ALGORITHM:
        return False
    return hmac.compare_digest(_digest(password, salt, iterations), digest)


def _digest(password: str, salt: str, iterations: int) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), iterations
    ).hex()


__all__ = [
    "DEFAULT_PASSWORD",
    "MAX_LENGTH",
    "MIN_LENGTH",
    "hash_password",
    "verify_password",
]
