"""Identity of Module 4. Read by ``app.registry`` and mirrored in the frontend."""

from __future__ import annotations

from typing import Final, Literal

NUMBER: Final = 4
NAME: Final = "Harvest Radar"
FOLDER: Final = "module_4"
ROUTE_PREFIX: Final = "/radar"
API_PREFIX: Final = "/api/v1/radar"
STATUS: Final[Literal["active", "placeholder", "deferred"]] = "active"
BUILD_ORDER: Final = 3
PURPOSE: Final = "Shows which fields are approaching harvest and ready for pickup."
