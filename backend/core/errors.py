"""Error types and the standard error envelope.

Every error response has the shape ``{"error": {"code", "message", "details"}}``.
Codes are stable machine-readable strings listed in ``docs/CONTRACTS.md``.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("sawie.errors")


class ErrorBody(BaseModel):
    code: str
    message: str
    details: Any = None


class ErrorEnvelope(BaseModel):
    error: ErrorBody


class AppError(Exception):
    """Base class for expected, client-visible errors."""

    status_code: int = 400
    code: str = "bad_request"

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        details: Any = None,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code
        if status_code is not None:
            self.status_code = status_code
        self.details = details


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class ConflictError(AppError):
    status_code = 409
    code = "conflict"


class ValidationAppError(AppError):
    status_code = 422
    code = "validation_error"


class UnauthorizedError(AppError):
    status_code = 401
    code = "unauthorized"


class ForbiddenError(AppError):
    status_code = 403
    code = "forbidden"


_HTTP_CODES: dict[int, str] = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    413: "payload_too_large",
    415: "unsupported_media_type",
    422: "validation_error",
    429: "too_many_requests",
}


def error_response(status_code: int, code: str, message: str, details: Any = None) -> JSONResponse:
    body = ErrorEnvelope(error=ErrorBody(code=code, message=message, details=details))
    return JSONResponse(status_code=status_code, content=body.model_dump(mode="json"))


def _field_path(loc: tuple[Any, ...] | list[Any]) -> str:
    parts = [str(p) for p in loc if p not in ("body", "query", "path", "header", "cookie")]
    return ".".join(parts) if parts else "__root__"


def register_exception_handlers(app: FastAPI) -> None:
    """Map every exception type onto the standard envelope."""

    @app.exception_handler(AppError)
    async def _app_error(_request: Request, exc: AppError) -> JSONResponse:
        return error_response(exc.status_code, exc.code, exc.message, exc.details)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_request: Request, exc: RequestValidationError) -> JSONResponse:
        fields = [
            {
                "field": _field_path(err.get("loc", ())),
                "location": str(err.get("loc", ("",))[0]),
                "message": err.get("msg", "Invalid value"),
                "type": err.get("type", "value_error"),
            }
            for err in exc.errors()
        ]
        return error_response(
            422, "validation_error", "One or more fields are invalid.", {"fields": fields}
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = _HTTP_CODES.get(exc.status_code, "http_error")
        message = exc.detail if isinstance(exc.detail, str) else "Request failed."
        return error_response(exc.status_code, code, message)

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        request_id = getattr(request.state, "request_id", None)
        return error_response(
            500,
            "internal_error",
            "An unexpected error occurred.",
            {"request_id": request_id} if request_id else None,
        )
