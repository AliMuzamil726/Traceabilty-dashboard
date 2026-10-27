"""Business logic for Module 3 (Fieldbook).

* :mod:`~module_3.services.formschema` - the schema-driven form engine
* :mod:`~module_3.services.books` - fieldbook lifecycle, locking, submit, timeline
* :mod:`~module_3.services.selectors` - the officer, farmer and field pickers
* :mod:`~module_3.services.photos` - photo validation and storage
* :mod:`~module_3.services.clock` - crop clock status
"""

from __future__ import annotations

from module_3 import meta
from module_3.services.books import FieldbookService
from module_3.services.selectors import SelectorService
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


__all__ = ["FieldbookService", "SelectorService", "get_meta"]
