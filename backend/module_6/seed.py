"""Reference data Module 6 owns: heap defaults per crop.

PLACEHOLDER VALUES TO CONFIRM WITH THE BUSINESS. Editable later in Settings; existing
rows are never overwritten.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from module_6.models import HeapConfig
from module_6.repository import HeapConfigRepository

#: crop -> (outturn %, bale kg, shiv %, dust %)
DEFAULT_CONFIG: dict[str, tuple[float, float, float | None, float | None]] = {
    "cotton": (34.0, 170.0, None, None),
    "hemp": (25.0, 250.0, 55.0, 15.0),
}


def run(session: Session) -> int:
    repo = HeapConfigRepository(session)
    inserted = 0
    for crop, (ratio, unit, shiv, dust) in DEFAULT_CONFIG.items():
        if repo.for_crop(crop) is None:
            repo.add(
                HeapConfig(
                    crop=crop,
                    default_outturn_ratio_pct=ratio,
                    default_bale_unit_kg=unit,
                    default_shiv_pct=shiv,
                    default_dust_pct=dust,
                )
            )
            inserted += 1
    return inserted
