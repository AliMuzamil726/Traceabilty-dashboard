"""Small in-process rate limiter for the farmer lookup endpoint.

Lookup takes an ID number and says whether that person is already registered, so it
must not be usable to test ID numbers in bulk. One process and one worker is the
deployment for this phase, so a fixed-window counter in memory is enough; when the
API runs behind several workers this moves to a shared store.

The implementation lives in :mod:`core.ratelimit` so every module shares one tested
limiter; this module only owns the endpoint's instance and its limit.
"""

from __future__ import annotations

from core.ratelimit import RateLimiter

#: Generous for an officer typing a CNIC, far too small to enumerate a 13 digit
#: number space.
lookup_limiter = RateLimiter()
"""Limiter for ``GET /api/v1/register/farmers/lookup``."""

__all__ = ["lookup_limiter"]
