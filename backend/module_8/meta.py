"""Identity of Module 8. Read by ``app.registry`` and mirrored in the frontend."""

from __future__ import annotations

from typing import Final, Literal

NUMBER: Final = 8
NAME: Final = "Settings"
FOLDER: Final = "module_8"
ROUTE_PREFIX: Final = "/settings"
API_PREFIX: Final = "/api/v1/settings"
STATUS: Final[Literal["active", "placeholder", "deferred"]] = "active"
BUILD_ORDER: Final = 8
PURPOSE: Final = "Administer people, lists, locations, parameters, the audit log and backups."
