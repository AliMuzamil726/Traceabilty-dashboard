"""Identity of Module 3. Read by ``app.registry`` and mirrored in the frontend."""

from __future__ import annotations

from typing import Final, Literal

NUMBER: Final = 3
NAME: Final = "Fieldbook"
FOLDER: Final = "module_3"
ROUTE_PREFIX: Final = "/fieldbook"
API_PREFIX: Final = "/api/v1/fieldbook"
STATUS: Final[Literal["active", "placeholder", "deferred"]] = "active"
BUILD_ORDER: Final = 2
PURPOSE: Final = "Season fieldbooks with step-by-step field records and photos."
