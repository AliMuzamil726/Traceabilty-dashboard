"""Business logic for Module 5 (Deliveries)."""

from __future__ import annotations

from module_5 import meta
from module_5.services.deliveries import DeliveryService, Skipped
from module_5.services.queries import DeliveryFilters, DeliveryQueries
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


__all__ = ["DeliveryFilters", "DeliveryQueries", "DeliveryService", "Skipped", "get_meta"]
