"""Identity of Module 1. Read by ``app.registry`` and mirrored in the frontend."""

from __future__ import annotations

from typing import Final, Literal

NUMBER: Final = 1
NAME: Final = "Dashboard / Home"
FOLDER: Final = "module_1"
ROUTE_PREFIX: Final = "/"
API_PREFIX: Final = "/api/v1/dashboard"
STATUS: Final[Literal["active", "placeholder", "deferred"]] = "active"
BUILD_ORDER: Final = 7
PURPOSE: Final = "Programme overview that reads from every other module."
