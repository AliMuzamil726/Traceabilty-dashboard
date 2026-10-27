"""Who may do what with heaps. The only place Module 6 checks roles.

Officers open heaps, add and remove deliveries, record bales and close a heap that
has no remainder. Only administrators void bales and close with a remainder, because
both change what the records say was produced.
"""

from __future__ import annotations

from core.deps import CurrentOfficer
from core.errors import ForbiddenError


def require_void_bale(officer: CurrentOfficer) -> None:
    if not officer.sees_all:
        raise ForbiddenError("Only an administrator can void a bale.", code="heap_admin_only")


def require_close_with_remainder(officer: CurrentOfficer) -> None:
    if not officer.sees_all:
        raise ForbiddenError(
            "Only an administrator can close with input left over.", code="heap_admin_only"
        )


def can_void_bale(officer: CurrentOfficer) -> bool:
    return officer.sees_all


def can_close_with_remainder(officer: CurrentOfficer) -> bool:
    return officer.sees_all
