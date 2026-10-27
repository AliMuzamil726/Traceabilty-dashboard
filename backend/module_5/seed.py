"""Reference data Module 5 owns: weight and moisture thresholds per crop.

Idempotent: a crop that already has a row is left alone.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from module_5.models import DeliveryConfig
from module_5.repository import ConfigRepository

#: crop -> (variance warn %, variance flag %, moisture warn %)
DEFAULT_CONFIG = {"cotton": (3.0, 5.0, 12.0), "hemp": (3.0, 5.0, 16.0)}


def run(session: Session) -> int:
    repo = ConfigRepository(session)
    inserted = 0
    for crop, (warn, flag, moisture) in DEFAULT_CONFIG.items():
        if repo.for_crop(crop) is None:
            repo.add(
                DeliveryConfig(
                    crop=crop,
                    variance_warn_pct=warn,
                    variance_flag_pct=flag,
                    moisture_warn_pct=moisture,
                )
            )
            inserted += 1
    return inserted
