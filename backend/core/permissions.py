"""Who may do what, in one place.

Every role check in the product goes through this module, so the rules can be listed
on one screen (Settings shows the matrix built from :data:`CAPABILITIES`) and changed
in one edit. There is no login yet: the acting officer comes from the ``X-Officer-Id``
header (``core.deps.get_current_officer``), and a role is ``officer``, ``staff`` or
``admin``. Staff work on every officer's records but cannot open Settings.

Two kinds of rule live here:

* **Capabilities**: a named action that a role either has or does not
  (``settings.manage``, ``farmer.create``). :func:`may` answers; :func:`require`
  raises :class:`~core.errors.ForbiddenError` with a stable error code.
* **Ownership**: an officer acts on the records they registered, an administrator on
  all of them. :func:`may_act_on` answers for any object carrying a registering
  officer id.

Lockout protection (the last administrator cannot be removed) lives in Module 8, not
here, because it needs to count rows.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from core.deps import CurrentOfficer
from core.errors import ForbiddenError
from shared.models.officer import ROLE_ADMIN, ROLE_OFFICER, ROLE_STAFF

ROLES: Final[tuple[str, ...]] = (ROLE_OFFICER, ROLE_STAFF, ROLE_ADMIN)


@dataclass(frozen=True)
class Capability:
    """One named action, the roles that hold it, and what to tell the person."""

    key: str
    module: int | None
    label: str
    description: str
    roles: tuple[str, ...]

    def held_by(self, role: str) -> bool:
        return role in self.roles


_BOTH: Final[tuple[str, ...]] = (ROLE_OFFICER, ROLE_STAFF, ROLE_ADMIN)
#: Staff work on every officer's records like an administrator, but never open Settings.
_STAFF: Final[tuple[str, ...]] = (ROLE_STAFF, ROLE_ADMIN)
_ADMIN: Final[tuple[str, ...]] = (ROLE_ADMIN,)

#: Every capability in the product. The Settings permissions matrix is generated from
#: this list, so a new rule appears on screen without a second edit.
CAPABILITIES: Final[tuple[Capability, ...]] = (
    Capability(
        "dashboard.view", 1, "See the dashboard", "Open the dashboard and its sections.", _BOTH
    ),
    Capability(
        "dashboard.view_all",
        1,
        "See every officer's work",
        "Switch the dashboard from 'My work' to 'All programme'.",
        _STAFF,
    ),
    Capability(
        "farmer.create", 2, "Register farmers", "Register a farmer and map their fields.", _BOTH
    ),
    Capability(
        "farmer.edit_own",
        2,
        "Edit own farmers",
        "Change a farmer they registered, and that farmer's fields.",
        _BOTH,
    ),
    Capability(
        "farmer.edit_any",
        2,
        "Edit any farmer",
        "Change a farmer registered by another officer.",
        _STAFF,
    ),
    Capability(
        "farmer.see_sensitive",
        2,
        "See full ID numbers",
        "See an unmasked ID number and phone for another officer's farmer.",
        _STAFF,
    ),
    Capability(
        "fieldbook.fill",
        3,
        "Fill in fieldbooks",
        "Open a fieldbook, save steps and submit it.",
        _BOTH,
    ),
    Capability(
        "radar.request_pickup", 4, "Request pickups", "Ask for a pickup from Harvest Radar.", _BOTH
    ),
    Capability(
        "delivery.record", 5, "Record deliveries", "Schedule, dispatch and receive loads.", _BOTH
    ),
    Capability(
        "heap.manage",
        6,
        "Manage heaps and batches",
        "Open a heap, add loads, record bales and close it.",
        _BOTH,
    ),
    Capability("qr.print", 7, "Print labels", "Generate and print QR labels.", _BOTH),
    Capability(
        "qr.revoke", 7, "Revoke codes", "Revoke a printed code so it stops resolving.", _STAFF
    ),
    Capability(
        "settings.manage",
        8,
        "Change settings",
        "Open Settings and change officers, lists, locations and parameters.",
        _ADMIN,
    ),
    Capability(
        "settings.preferences",
        8,
        "Change own preferences",
        "Change their own sidebar, density and default crop.",
        _BOTH,
    ),
    Capability("audit.read", 8, "Read the audit log", "Search and export the audit log.", _ADMIN),
    Capability(
        "backup.manage",
        8,
        "Back up and restore",
        "Create, download, delete and restore database backups.",
        _ADMIN,
    ),
)

BY_KEY: Final[dict[str, Capability]] = {c.key: c for c in CAPABILITIES}


def capability(key: str) -> Capability:
    try:
        return BY_KEY[key]
    except KeyError:  # pragma: no cover - a typo in a call, caught by tests
        raise KeyError(f"Unknown capability {key!r}. Add it to core.permissions.") from None


def may(officer: CurrentOfficer, key: str) -> bool:
    """True when this officer's role holds the capability."""
    return capability(key).held_by(officer.role)


def require(officer: CurrentOfficer, key: str) -> None:
    """Raise :class:`ForbiddenError` unless the officer holds the capability."""
    cap = capability(key)
    if cap.held_by(officer.role):
        return
    if cap.roles in (_ADMIN, _STAFF):
        raise ForbiddenError(
            "Administrator role required.", code="admin_required", details={"capability": key}
        )
    raise ForbiddenError(
        f"This account cannot {cap.label.lower()}.", code="forbidden", details={"capability": key}
    )


def may_act_on(officer: CurrentOfficer, registered_by: str | None) -> bool:
    """Ownership rule: own records, or anything when administrator (DECISIONS D-110)."""
    return officer.sees_all or registered_by == officer.id


def matrix() -> list[dict[str, object]]:
    """The permissions table, for the read-only Settings screen."""
    return [
        {
            "key": c.key,
            "module": c.module,
            "label": c.label,
            "description": c.description,
            "officer": c.held_by(ROLE_OFFICER),
            "staff": c.held_by(ROLE_STAFF),
            "admin": c.held_by(ROLE_ADMIN),
        }
        for c in CAPABILITIES
    ]


__all__ = [
    "CAPABILITIES",
    "ROLES",
    "Capability",
    "capability",
    "matrix",
    "may",
    "may_act_on",
    "require",
]
