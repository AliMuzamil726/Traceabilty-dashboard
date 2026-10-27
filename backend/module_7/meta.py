"""Identity of Module 7. Read by ``app.registry`` and mirrored in the frontend."""

from __future__ import annotations

from typing import Final, Literal

NUMBER: Final = 7
NAME: Final = "QR Tracing"
FOLDER: Final = "module_7"
ROUTE_PREFIX: Final = "/qr"
API_PREFIX: Final = "/api/v1/qr"
STATUS: Final[Literal["active", "placeholder", "deferred"]] = "active"
BUILD_ORDER: Final = 6
PURPOSE: Final = "QR-tagged bales traced back to farmers and fields."
