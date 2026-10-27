"""QR images on the backend: PNG and SVG, error correction M, a 4-module quiet zone."""

from __future__ import annotations

import io

import qrcode
import qrcode.image.svg
from qrcode.constants import ERROR_CORRECT_M

INK = "#15221B"  # the design system's ink, near black, on white
QUIET_ZONE = 4


def trace_url(base_url: str, token: str) -> str:
    return f"{base_url.rstrip('/')}/trace/{token}"


def is_local(base_url: str) -> bool:
    lowered = base_url.lower()
    return "localhost" in lowered or "127.0.0.1" in lowered


def _qr(data: str, box_size: int = 10) -> qrcode.QRCode:
    qr = qrcode.QRCode(error_correction=ERROR_CORRECT_M, box_size=box_size, border=QUIET_ZONE)
    qr.add_data(data)
    qr.make(fit=True)
    return qr


def png(data: str, *, box_size: int = 10) -> bytes:
    image = _qr(data, box_size).make_image(fill_color=INK, back_color="white")
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def svg(data: str) -> bytes:
    image = _qr(data).make_image(image_factory=qrcode.image.svg.SvgPathImage)
    buf = io.BytesIO()
    image.save(buf)
    return buf.getvalue()


def pil_image(data: str, box_size: int = 10):  # type: ignore[no-untyped-def]
    return _qr(data, box_size).make_image(fill_color=INK, back_color="white").get_image()
