"""Business logic for Module 6 (Heap)."""

from __future__ import annotations

from module_6 import meta
from module_6.services.heaps import HeapService, Skipped
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


__all__ = ["HeapService", "Skipped", "get_meta"]
