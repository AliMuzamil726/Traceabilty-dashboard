"""Business logic for Module 2 (Register Farmer).

``services`` is a package rather than a single file because this module carries a real
geometry engine; splitting it keeps each concern readable and separately testable:

* :mod:`~module_2.services.validators` - identifier normalisation and validation
* :mod:`~module_2.services.ids` - SAWIE ID and field ID allocation
* :mod:`~module_2.services.geometry` - polygon validation, area and the overlap rule
* :mod:`~module_2.services.farmers` - registration, lookup, profile
* :mod:`~module_2.services.fields` - field creation, editing, deletion, map layer
* :mod:`~module_2.services.locations` - the province to tehsil cascade
* :mod:`~module_2.services.postcode` - UK postcode to county and region
* :mod:`~module_2.services.ratelimit` - lookup rate limiting

Services own transactions: each public write method calls ``session.commit()`` itself.
"""

from __future__ import annotations

from module_2 import meta
from module_2.services.farmers import FarmerService, current_season_year
from module_2.services.fields import FieldService
from module_2.services.locations import LocationService
from module_2.services.postcode import PostcodeService
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


__all__ = [
    "FarmerService",
    "FieldService",
    "LocationService",
    "PostcodeService",
    "current_season_year",
    "get_meta",
]
