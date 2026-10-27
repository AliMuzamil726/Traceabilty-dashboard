"""HTTP routes for Module 7 (QR Tracing), mounted at ``/api/v1/qr``.

``GET /public/{token}`` is the only route meant for anyone: rate limited, cached for 60
seconds, privacy filtered, and answering unknown and revoked codes identically.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, Path, Query, Request
from fastapi.responses import JSONResponse, Response
from sqlalchemy.orm import Session

from core.config import Settings
from core.deps import CurrentOfficer, get_current_officer, get_db, get_settings_dep
from core.errors import AppError, NotFoundError
from module_7 import meta, services
from module_7.models import CHANNEL_INTERNAL, CHANNEL_PUBLIC
from module_7.schemas import ReasonIn, SerialsIn
from module_7.services import images, scans
from shared.schemas import ModuleMetaOut

router = APIRouter(prefix=meta.API_PREFIX, tags=[f"module_{meta.NUMBER}"])

INVALID_MESSAGE = "This code is not valid"


class InvalidCodeError(AppError):
    status_code = 404
    code = "qr_invalid"


class RateLimitedError(AppError):
    status_code = 429
    code = "rate_limited"


def get_service(
    session: Session = Depends(get_db), settings: Settings = Depends(get_settings_dep)
) -> services.QrService:
    return services.QrService(session, settings)


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


# --------------------------------------------------------------------------- public


@router.get("/public/{token}", summary="Public, privacy-filtered trace of a code (no login)")
def public_trace(
    request: Request,
    background: BackgroundTasks,
    token: str = Path(..., max_length=64),
    service: services.QrService = Depends(get_service),
) -> JSONResponse:
    ip = _client_ip(request)
    allowed, retry = scans.public_limiter.check(
        scans.ip_hash(ip, service.settings.qr_ip_salt) or "unknown"
    )
    if not allowed:
        raise RateLimitedError(
            "Too many lookups. Try again shortly.", details={"retry_after_seconds": retry}
        )
    found = service.public_trace(token.strip().upper())
    if found is None:
        raise InvalidCodeError(INVALID_MESSAGE)
    payload, row = found
    scan = {
        "token_id": row.id,
        "token_type": row.token_type,
        "heap_id": row.heap_id,
        "bale_serial": row.bale_serial,
    }
    # End the read transaction now: the scan is logged in its own session after the
    # response, and SQLite's write lock (BEGIN IMMEDIATE) must not still be held then.
    service.session.rollback()
    _log_scan(background, request, service, scan, CHANNEL_PUBLIC)
    return JSONResponse(
        content=_jsonable(payload),
        headers={"Cache-Control": "public, max-age=60"},
    )


def _log_scan(
    background: BackgroundTasks,
    request: Request,
    service: services.QrService,
    scan: dict[str, Any],
    channel: str,
) -> None:
    background.add_task(
        scans.record_scan,
        request.app.state.db,
        scan["token_id"],
        channel=channel,
        ip=_client_ip(request),
        ua=request.headers.get("user-agent"),
        salt=service.settings.qr_ip_salt,
        token_type=scan["token_type"],
        heap_id=scan["heap_id"],
        bale_serial=scan["bale_serial"],
    )


def _jsonable(value: Any) -> Any:
    from fastapi.encoders import jsonable_encoder

    return jsonable_encoder(value)


# --------------------------------------------------------------------------- internal


@router.get("/meta", response_model=ModuleMetaOut, summary="Module identity and build status")
def get_meta() -> ModuleMetaOut:
    return services.get_meta()


@router.get("/lots", summary="Heaps and batches with their codes, plus the base URL in use")
def lots(
    crop: str | None = Query(None, pattern=r"^(cotton|hemp)$"),
    site_id: str | None = Query(None, max_length=36),
    officer: CurrentOfficer = Depends(get_current_officer),
    service: services.QrService = Depends(get_service),
) -> dict[str, Any]:
    del officer
    return {
        "items": service.lots(crop=crop, site_id=site_id or None),
        "base_url": service.base_url,
        "base_url_is_local": images.is_local(service.base_url),
    }


@router.get("/lots/{heap_id}/overview", summary="One lot: code, summary and scan statistics")
def overview(
    heap_id: str = Path(..., max_length=36),
    officer: CurrentOfficer = Depends(get_current_officer),
    service: services.QrService = Depends(get_service),
) -> dict[str, Any]:
    del officer
    return service.overview(heap_id)


@router.get("/bales", summary="Bales of a lot with code status, prints and scans")
def bales(
    heap_id: str = Query(..., max_length=36),
    officer: CurrentOfficer = Depends(get_current_officer),
    service: services.QrService = Depends(get_service),
) -> list[dict[str, Any]]:
    del officer
    return service.bales(heap_id)


@router.get("/tokens/{token}/image.png", summary="QR image (PNG)")
def image_png(
    token: str = Path(..., max_length=16),
    size: int = Query(10, ge=2, le=40, description="Pixels per module"),
    officer: CurrentOfficer = Depends(get_current_officer),
    service: services.QrService = Depends(get_service),
) -> Response:
    del officer
    row = service.token_for_image(token)
    return Response(
        images.png(service.url(row.token), box_size=size),
        media_type="image/png",
        headers={"Content-Disposition": f'inline; filename="{row.bale_serial or row.heap_id}.png"'},
    )


@router.get("/tokens/{token}/image.svg", summary="QR image (SVG)")
def image_svg(
    token: str = Path(..., max_length=16),
    officer: CurrentOfficer = Depends(get_current_officer),
    service: services.QrService = Depends(get_service),
) -> Response:
    del officer
    row = service.token_for_image(token)
    return Response(
        images.svg(service.url(row.token)),
        media_type="image/svg+xml",
        headers={"Content-Disposition": f'inline; filename="{row.bale_serial or row.heap_id}.svg"'},
    )


@router.post("/labels", summary="A4 label sheet (PDF) for the chosen bales; counts each print")
def label_sheet(
    body: SerialsIn,
    officer: CurrentOfficer = Depends(get_current_officer),
    service: services.QrService = Depends(get_service),
) -> Response:
    content = service.labels_pdf(body.serials, officer)
    name = f"labels_{datetime.now(UTC).strftime('%Y%m%d_%H%M')}.pdf"
    return Response(
        content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )


@router.get("/bales/{serial}/label.png", summary="One label as PNG; counts as a print")
def label_png(
    serial: str = Path(..., max_length=48),
    officer: CurrentOfficer = Depends(get_current_officer),
    service: services.QrService = Depends(get_service),
) -> Response:
    return Response(
        service.label_png(serial, officer),
        media_type="image/png",
        headers={"Content-Disposition": f'attachment; filename="{serial}_label.png"'},
    )


@router.post("/images.zip", summary="QR images (PNG) of the chosen bales, as a ZIP")
def images_zip(
    body: SerialsIn,
    officer: CurrentOfficer = Depends(get_current_officer),
    service: services.QrService = Depends(get_service),
) -> Response:
    del officer
    return Response(
        service.images_zip(body.serials),
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="qr_codes.zip"'},
    )


@router.post("/tokens/{token}/revoke", summary="Revoke a code (administrators, reason required)")
def revoke(
    body: ReasonIn,
    token: str = Path(..., max_length=16),
    officer: CurrentOfficer = Depends(get_current_officer),
    service: services.QrService = Depends(get_service),
) -> dict[str, Any]:
    row = services.TokenService(service.session).revoke(token, officer, body.reason)
    return {
        "token": row.token,
        "status": row.status,
        "revoked_at": row.revoked_at,
        "revoke_reason": row.revoke_reason,
    }


@router.post("/bales/{serial}/regenerate", summary="New code for a bale; the old one is revoked")
def regenerate(
    body: ReasonIn,
    serial: str = Path(..., max_length=48),
    officer: CurrentOfficer = Depends(get_current_officer),
    service: services.QrService = Depends(get_service),
) -> dict[str, Any]:
    row = service.regenerate(serial, officer, body.reason)
    return {
        "token": row.token,
        "status": row.status,
        "bale_serial": row.bale_serial,
        "trace_url": service.url(row.token),
    }


@router.get("/trace/bale/{serial}", summary="Full internal chain for a bale")
def trace_bale(
    serial: str = Path(..., max_length=48),
    officer: CurrentOfficer = Depends(get_current_officer),
    service: services.QrService = Depends(get_service),
) -> dict[str, Any]:
    return service.internal_bale(serial, officer)


@router.get("/trace/heap/{heap_id}", summary="Full internal chain for a heap or batch")
def trace_heap(
    heap_id: str = Path(..., max_length=36),
    officer: CurrentOfficer = Depends(get_current_officer),
    service: services.QrService = Depends(get_service),
) -> dict[str, Any]:
    return service.internal_heap(heap_id, officer)


@router.get("/resolve", summary="A code, bale serial or trace link to its record")
def resolve(
    request: Request,
    background: BackgroundTasks,
    q: str = Query(..., max_length=500),
    officer: CurrentOfficer = Depends(get_current_officer),
    service: services.QrService = Depends(get_service),
) -> dict[str, Any]:
    del officer
    r = service.resolve(q)
    if r.token is not None:
        row = service.tokens.by_token(r.token)
        if row is not None:
            scan = {
                "token_id": row.id,
                "token_type": row.token_type,
                "heap_id": row.heap_id,
                "bale_serial": row.bale_serial,
            }
            service.session.rollback()  # release the write lock before the scan is logged
            _log_scan(background, request, service, scan, CHANNEL_INTERNAL)
    return {
        "kind": r.kind,
        "heap_id": r.heap_id,
        "bale_serial": r.bale_serial,
        "token": r.token,
        "token_status": r.token_status,
    }


@router.get("/scans/summary", summary="Scan counts, optionally for one lot")
def scan_summary(
    heap_id: str | None = Query(None, max_length=36),
    officer: CurrentOfficer = Depends(get_current_officer),
    service: services.QrService = Depends(get_service),
) -> dict[str, Any]:
    del officer
    if heap_id:
        from module_6 import public_api as heaps

        heap = heaps.get_heap(service.session, heap_id)
        if heap is None:
            raise NotFoundError("That heap does not exist.", code="heap_not_found")
        heap_id = heap.heap_id
    return service.scan_summary(heap_id)
