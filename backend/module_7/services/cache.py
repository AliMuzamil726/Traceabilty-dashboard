"""60-second cache for public trace payloads, cleared whenever a code or a heap changes."""

from __future__ import annotations

import threading
import time
from typing import Any

TTL_SECONDS = 60.0
_lock = threading.Lock()
_store: dict[tuple[str, str], tuple[float, Any]] = {}


def get(key: tuple[str, str]) -> Any:
    with _lock:
        hit = _store.get(key)
        if hit is not None and time.monotonic() - hit[0] < TTL_SECONDS:
            return hit[1]
        return None


def put(key: tuple[str, str], value: Any) -> None:
    with _lock:
        if len(_store) > 2000:
            _store.clear()
        _store[key] = (time.monotonic(), value)


def invalidate() -> None:
    with _lock:
        _store.clear()
