"""Settings talks to the modules that own their configuration, never to their tables.

Each owning module exposes ``get_config``, ``update_config`` and, where a change is
worth seeing before it is made, ``preview_config_change`` on its ``config_api``. This
file is the thin layer that routes a Settings request to the right owner, commits once
and publishes ``config.changed`` so every cache drops what it holds.

Who owns what:

======================  =========================================================
Crop clock              Module 3 (``module_3.public_api``)
Delivery tolerances     Module 5 (``module_5.public_api``)
Heap and batch defaults Module 6 (``module_6.public_api``)
Alert thresholds        Module 1, stored as generic settings (``alerts.*``)
======================  =========================================================

Each is reached through the owning module's ``public_api``, which is the only file
another module may import (``backend/tests/test_architecture.py``).

Alert thresholds are plain numbers with no table of their own, so they live in the
registry and are written through :class:`~module_8.services.values.SettingsValueService`
like any other setting; this file only reads them back in the same shape as the others,
so one screen can render all four blocks.
"""

from __future__ import annotations

from typing import Any, Final

from sqlalchemy.orm import Session

from core.deps import CurrentOfficer
from core.errors import NotFoundError, ValidationAppError
from core.events import CONFIG_CHANGED, bus
from module_1 import public_api as alerts_config
from module_3 import public_api as clock_config
from module_5 import public_api as delivery_config
from module_6 import public_api as heap_config

#: The blocks a client may ask for, and the module that owns each one.
BLOCKS: Final[tuple[str, ...]] = ("clock", "delivery", "heap", "alerts")

OWNERS: Final[dict[str, int]] = {"clock": 3, "delivery": 5, "heap": 6, "alerts": 1}


class ConfigService:
    """One entry point for the four owned configuration blocks."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def _check(self, block: str) -> str:
        if block not in BLOCKS:
            raise NotFoundError(
                f"Unknown configuration block {block!r}.", code="unknown_config_block"
            )
        return block

    # ------------------------------------------------------------------ reading

    def get(self, block: str) -> dict[str, Any]:
        self._check(block)
        if block == "clock":
            return clock_config.get_config(self.session)
        if block == "delivery":
            return delivery_config.get_config(self.session)
        if block == "heap":
            return heap_config.get_config(self.session)
        return alerts_config.get_config(self.session)

    def all_blocks(self) -> dict[str, Any]:
        return {block: self.get(block) for block in BLOCKS}

    # ------------------------------------------------------------------ writing

    def update(
        self,
        block: str,
        values: dict[str, Any],
        officer: CurrentOfficer,
        expected_version: int | None = None,
    ) -> dict[str, Any]:
        """Hand the change to the owning module, then commit and invalidate caches."""
        self._check(block)
        if block == "alerts":
            raise ValidationAppError(
                "Alert thresholds are saved one at a time through the settings values API.",
                code="use_values_api",
            )
        if not isinstance(values, dict) or not values:
            raise ValidationAppError("Send the values to change.", code="empty_update")

        owner = {
            "clock": clock_config,
            "delivery": delivery_config,
            "heap": heap_config,
        }[block]
        result = owner.update_config(self.session, values, officer.id, expected_version)
        self.session.commit()
        bus.publish(
            CONFIG_CHANGED,
            {"key": result.get("key", f"config.{block}"), "group": block},
            officer_id=officer.id,
            session=self.session,
        )
        return self.get(block)

    # ----------------------------------------------------------------- previews

    def preview(self, block: str, values: dict[str, Any]) -> dict[str, Any]:
        """What a proposed change would do, without writing anything."""
        self._check(block)
        if block != "clock":
            raise ValidationAppError(
                "Only the crop clock has an impact preview.", code="no_preview"
            )
        return clock_config.preview_config_change(self.session, values)


__all__ = ["BLOCKS", "OWNERS", "ConfigService"]
