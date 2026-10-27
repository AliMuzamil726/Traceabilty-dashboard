"""Business logic for Module 7 (QR Tracing)."""

from __future__ import annotations

from module_7 import meta
from module_7.services.qr import QrService, Resolved
from module_7.services.tokens import TokenService
from shared.schemas import ModuleMetaOut


def get_meta() -> ModuleMetaOut:
    return ModuleMetaOut(
        number=meta.NUMBER,
        name=meta.NAME,
        route_prefix=meta.ROUTE_PREFIX,
        api_prefix=meta.API_PREFIX,
        status=meta.STATUS,
        build_order=meta.BUILD_ORDER,
        purpose=meta.PURPOSE,
    )


__all__ = ["QrService", "Resolved", "TokenService", "get_meta"]
