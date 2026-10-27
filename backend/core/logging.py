"""Logging setup with a per-request ID that appears on every log line."""

from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Awaitable, Callable
from contextvars import ContextVar

from starlette.requests import Request
from starlette.responses import Response

REQUEST_ID_HEADER = "X-Request-Id"
_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)

access_logger = logging.getLogger("sawie.access")


def get_request_id() -> str | None:
    return _request_id.get()


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = _request_id.get() or "-"
        return True


def configure_logging(level: str = "INFO") -> None:
    """Idempotent root logging configuration."""
    root = logging.getLogger()
    root.setLevel(level.upper())
    for handler in root.handlers:
        if getattr(handler, "_sawie", False):
            return
    handler = logging.StreamHandler()
    handler._sawie = True  # type: ignore[attr-defined]
    handler.addFilter(RequestIdFilter())
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)-7s [%(request_id)s] %(name)s: %(message)s")
    )
    root.addHandler(handler)


async def request_id_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Attach a request id (incoming header or new UUID) and log one access line."""
    incoming = request.headers.get(REQUEST_ID_HEADER, "")
    request_id = incoming[:64] if incoming else uuid.uuid4().hex
    token = _request_id.set(request_id)
    request.state.request_id = request_id
    started = time.perf_counter()
    try:
        response = await call_next(request)
        response.headers[REQUEST_ID_HEADER] = request_id
        access_logger.info(
            "%s %s -> %s (%.1f ms)",
            request.method,
            request.url.path,
            response.status_code,
            (time.perf_counter() - started) * 1000,
        )
        return response
    finally:
        _request_id.reset(token)
