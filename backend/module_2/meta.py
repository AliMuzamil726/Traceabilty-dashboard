"""Identity of Module 2. Read by ``app.registry`` and mirrored in the frontend."""

from __future__ import annotations

from typing import Final, Literal

NUMBER: Final = 2
NAME: Final = "Register Farmer"
FOLDER: Final = "module_2"
ROUTE_PREFIX: Final = "/register"
API_PREFIX: Final = "/api/v1/register"
STATUS: Final[Literal["active", "placeholder", "deferred"]] = "active"
BUILD_ORDER: Final = 1
PURPOSE: Final = "Register farmers and map their fields."
