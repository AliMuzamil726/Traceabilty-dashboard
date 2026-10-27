"""Reference data Module 3 owns: the crop clock.

Run at every startup through ``app.registry.run_module_seeds``. Idempotent: a crop that
already has a row is left alone, so values edited later (in Settings) are never
overwritten.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from module_3.models import CropClockConfig
from module_3.repository import CropClockRepository
from module_3.services.clock import DEFAULT_CLOCKS


def run(session: Session) -> int:
    repo = CropClockRepository(session)
    inserted = 0
    for crop, (approach, ready, window_end) in DEFAULT_CLOCKS.items():
        if repo.for_crop(crop) is None:
            repo.add(
                CropClockConfig(
                    crop=crop, approach_day=approach, ready_day=ready, window_end_day=window_end
                )
            )
            inserted += 1
    return inserted
