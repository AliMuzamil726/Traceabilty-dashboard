"""A small in-process fixed-window rate limiter, shared by modules that need one.

One process and one worker is the deployment for this phase, so a counter in memory is
enough; when the API runs behind several workers this moves to a shared store.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass

#: Requests allowed per key per window by default.
DEFAULT_LIMIT = 60
DEFAULT_WINDOW_SECONDS = 60.0

#: Above this many keys the limiter drops the windows that have already expired.
#: Without it, one entry per scanner IP or token would stay in memory for ever.
PURGE_THRESHOLD = 1024


@dataclass
class _Window:
    started_at: float
    count: int


class RateLimiter:
    def __init__(
        self, limit: int = DEFAULT_LIMIT, window_seconds: float = DEFAULT_WINDOW_SECONDS
    ) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self._windows: dict[str, _Window] = {}
        self._lock = threading.Lock()

    def check(self, key: str, *, now: float | None = None) -> tuple[bool, int]:
        """Count one request against ``key``. Returns ``(allowed, retry_after_seconds)``."""
        moment = now if now is not None else time.monotonic()
        with self._lock:
            if len(self._windows) >= PURGE_THRESHOLD:
                self._purge(moment)
            window = self._windows.get(key)
            if window is None or moment - window.started_at >= self.window_seconds:
                self._windows[key] = _Window(started_at=moment, count=1)
                return True, 0
            if window.count >= self.limit:
                retry_after = int(self.window_seconds - (moment - window.started_at)) + 1
                return False, max(retry_after, 1)
            window.count += 1
            return True, 0

    def _purge(self, moment: float) -> None:
        """Drop expired windows. Caller holds the lock."""
        expired = [
            key
            for key, window in self._windows.items()
            if moment - window.started_at >= self.window_seconds
        ]
        for key in expired:
            del self._windows[key]

    def reset(self) -> None:
        """Clear every window (used by tests)."""
        with self._lock:
            self._windows.clear()
