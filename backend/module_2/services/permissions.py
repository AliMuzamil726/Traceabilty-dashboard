"""Who may change a farmer and their fields.

The rule every module follows: an officer acts for the farmers they registered, and an
administrator acts for all. Reading is wider (other officers see masked details), but
any write to a farmer or a field goes through :func:`require_may_act` (audit F-11).

Registering an existing ID number again (``POST /farmers``) is not covered here: that is
the specified re-registration flow, and it never hands the farmer to the new officer.
"""

from __future__ import annotations

from core.deps import CurrentOfficer
from core.errors import ForbiddenError
from module_2.models import Farmer


def may_act(farmer: Farmer, officer: CurrentOfficer) -> bool:
    return officer.sees_all or farmer.registered_by == officer.id


def require_may_act(farmer: Farmer, officer: CurrentOfficer) -> None:
    if not may_act(farmer, officer):
        raise ForbiddenError(
            "This farmer was registered by another officer. Only they or an administrator "
            "can change the farmer or their fields.",
            code="farmer_forbidden",
            details={"farmer_id": farmer.id, "sawie_id": farmer.sawie_id},
        )


__all__ = ["may_act", "require_may_act"]
