"""Identity of Module 5. Read by ``app.registry`` and mirrored in the frontend."""

from __future__ import annotations

from typing import Final, Literal

NUMBER: Final = 5
NAME: Final = "Deliveries"
FOLDER: Final = "module_5"
ROUTE_PREFIX: Final = "/deliveries"
API_PREFIX: Final = "/api/v1/deliveries"
STATUS: Final[Literal["active", "placeholder", "deferred"]] = "active"
BUILD_ORDER: Final = 4
PURPOSE: Final = (
    "Schedule pickups, dispatch loads in transit, and receive them at the ginner "
    "or processor gate (farm to gate)."
)
