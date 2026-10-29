"""Identity of Module 9 (Gate Reception). Read by ``app.registry``."""

from __future__ import annotations

from typing import Final, Literal

NUMBER: Final = 9
NAME: Final = "Gate Reception"
FOLDER: Final = "module_9"
ROUTE_PREFIX: Final = "/gate"
API_PREFIX: Final = "/api/v1/gate"
STATUS: Final[Literal["active", "placeholder", "deferred"]] = "active"
BUILD_ORDER: Final = 9
PURPOSE: Final = (
    "Record the arrival of in-transit deliveries at the ginner or processor gate: "
    "weighbridge reading, moisture check, vehicle inspection and officer sign-off."
)
