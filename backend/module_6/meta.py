"""Identity of Module 6. Read by ``app.registry`` and mirrored in the frontend."""

from __future__ import annotations

from typing import Final, Literal

NUMBER: Final = 6
NAME: Final = "Heap"
FOLDER: Final = "module_6"
ROUTE_PREFIX: Final = "/heaps"
API_PREFIX: Final = "/api/v1/heaps"
STATUS: Final[Literal["active", "placeholder", "deferred"]] = "active"
BUILD_ORDER: Final = 5
PURPOSE: Final = "Group deliveries into a heap (cotton) or batch (hemp) and produce bales."
