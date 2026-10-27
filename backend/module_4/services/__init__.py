"""Business logic for Module 4 (Harvest Radar)."""

from __future__ import annotations

from module_4 import meta
from module_4.services.pickups import PickupService, Skipped
from module_4.services.radar import RadarFilters, RadarService
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


__all__ = ["PickupService", "RadarFilters", "RadarService", "Skipped", "get_meta"]
