"""A small time-boxed cache for Radar's computed views.

Results are kept for 30 seconds, keyed by the database and the full set of filters, and
dropped at once when an event says the underlying data changed (a fieldbook step, a
field change, a pickup request). Process-local: each API worker has its own copy, which
is fine because entries live only seconds and every write clears them.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable, Hashable
from typing import Any, TypeVar

TTL_SECONDS = 30.0
_MAX_ENTRIES = 256

T = TypeVar("T")

_lock = threading.Lock()
_store: dict[Hashable, tuple[float, Any]] = {}
_generation = 0


def get_or_compute(key: Hashable, compute: Callable[[], T], *, ttl: float = TTL_SECONDS) -> T:
    now = time.monotonic()
    with _lock:
        hit = _store.get(key)
        if hit is not None and now - hit[0] < ttl:
            return hit[1]  # type: ignore[no-any-return]
        generation = _generation
    value = compute()
    with _lock:
        # Do not keep a value computed while an invalidation happened.
        if generation == _generation:
            if len(_store) >= _MAX_ENTRIES:
                _store.clear()
            _store[key] = (time.monotonic(), value)
    return value


def invalidate() -> None:
    global _generation
    with _lock:
        _store.clear()
        _generation += 1


def size() -> int:
    with _lock:
        return len(_store)
