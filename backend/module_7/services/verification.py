"""The public verification panel. Pure: facts in, ticks out. Failures are shown, not hidden."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class Check:
    key: str
    label: str
    passed: bool
    detail: str


def checks(
    *,
    fieldbook_statuses: Sequence[str | None],
    deliveries: Sequence[tuple[str, float | None]],
    heap_status: str,
    bales_weight_kg: Decimal,
    expected_output_kg: Decimal,
    crop: str = "cotton",
) -> list[Check]:
    """``fieldbook_statuses``: one per contributing field and season (None when missing).
    ``deliveries``: (status, weighbridge kg) for each delivery in the heap."""
    submitted = sum(1 for s in fieldbook_statuses if s == "submitted")
    total_books = len(fieldbook_statuses)
    weighed = sum(1 for status, kg in deliveries if status == "delivered" and kg and kg > 0)
    lot_word = "Heap" if crop == "cotton" else "Batch"
    return [
        Check(
            "fieldbooks_submitted",
            "All contributing fieldbooks submitted",
            total_books > 0 and submitted == total_books,
            f"{submitted} of {total_books} submitted",
        ),
        Check(
            "deliveries_weighed",
            "All deliveries delivered with weighbridge records",
            len(deliveries) > 0 and weighed == len(deliveries),
            f"{weighed} of {len(deliveries)} weighed at the gate",
        ),
        Check(
            "heap_closed",
            f"{lot_word} closed after processing",
            heap_status == "closed",
            "Closed" if heap_status == "closed" else "Still open",
        ),
        Check(
            "mass_balance",
            "Mass balance within limits",
            bales_weight_kg <= expected_output_kg,
            f"{bales_weight_kg} kg baled of {expected_output_kg} kg expected",
        ),
    ]
