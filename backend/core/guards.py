"""Guard registry: lets downstream modules veto actions owned by upstream modules.

Example: Module 2 owns fields but must not delete a field that already has a
fieldbook (Module 3) or a delivery (Module 5). Instead of importing those modules,
Module 2 calls ``guards.enforce(FIELD_CAN_DELETE, field_id=...)`` and Modules 3 and
5 register checks for that guard name at startup.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from core.errors import ConflictError

logger = logging.getLogger("sawie.guards")

FIELD_CAN_DELETE = "field.can_delete"
FIELD_CAN_EDIT_GEOMETRY = "field.can_edit_geometry"
#: Module 5 asks before an administrator corrects a delivered delivery (Module 6 checks).
DELIVERY_CAN_CORRECT = "delivery.can_correct"
#: Module 5 asks before taking a delivery out of its heap (Module 6 checks).
DELIVERY_CAN_UNASSIGN = "delivery.can_unassign"


@dataclass(frozen=True)
class GuardResult:
    allowed: bool
    code: str | None = None
    reason: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def allow() -> GuardResult:
        return GuardResult(allowed=True)

    @staticmethod
    def deny(code: str, reason: str, **details: Any) -> GuardResult:
        return GuardResult(allowed=False, code=code, reason=reason, details=details)


GuardCheck = Callable[..., GuardResult]


@dataclass(frozen=True)
class GuardOutcome:
    """Aggregate result of every check registered for a guard."""

    allowed: bool
    denials: list[GuardResult]


class GuardRegistry:
    def __init__(self) -> None:
        self._checks: dict[str, list[tuple[str, GuardCheck]]] = defaultdict(list)

    def register(self, guard_name: str, check: GuardCheck, *, owner: str) -> None:
        """Register ``check`` for ``guard_name``. ``owner`` names the registering module."""
        entry = (owner, check)
        if entry not in self._checks[guard_name]:
            self._checks[guard_name].append(entry)

    def registered(self, guard_name: str) -> list[str]:
        return [owner for owner, _ in self._checks.get(guard_name, [])]

    def clear(self) -> None:
        self._checks.clear()

    def check(self, guard_name: str, **context: Any) -> GuardOutcome:
        """Run every check; collect all denials so the UI can explain each reason."""
        denials: list[GuardResult] = []
        for owner, check in self._checks.get(guard_name, []):
            result = check(**context)
            if not result.allowed:
                logger.info("Guard %s denied by %s: %s", guard_name, owner, result.code)
                denials.append(result)
        return GuardOutcome(allowed=not denials, denials=denials)

    def enforce(self, guard_name: str, **context: Any) -> None:
        """Raise :class:`ConflictError` with every denial reason if any check denies."""
        outcome = self.check(guard_name, **context)
        if outcome.allowed:
            return
        first = outcome.denials[0]
        raise ConflictError(
            first.reason or "This action is not allowed.",
            code=first.code or "guard_denied",
            details={
                "guard": guard_name,
                "reasons": [
                    {"code": d.code, "reason": d.reason, **d.details} for d in outcome.denials
                ],
            },
        )


guards = GuardRegistry()
"""Process-wide guard registry used by the application."""
