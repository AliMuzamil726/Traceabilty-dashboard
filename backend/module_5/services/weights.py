"""Weight variance and moisture checks. Pure functions, no database.

Variance compares the weighbridge weight with the best earlier figure: the field weight
when the driver recorded one at dispatch, otherwise the estimated quantity from the
pickup request. Percentages are rounded to two decimals (half up) before the level is
decided, so 2.99 is ok, 3.00 is warn and 5.00 is flag at the default thresholds.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from module_5.models import LEVEL_FLAG, LEVEL_OK, LEVEL_WARN

KG_PER_MAUND = Decimal(40)
_CENT = Decimal("0.01")
_TENTH = Decimal("0.1")


@dataclass(frozen=True)
class Variance:
    reference_kg: float | None
    reference: str | None  # field_weight | estimate | None
    variance_kg: float | None
    variance_pct: float | None
    level: str | None


def _d(value: float) -> Decimal:
    return Decimal(str(value))


def variance(
    weighbridge_kg: float,
    *,
    field_weight_kg: float | None,
    estimated_kg: float | None,
    warn_pct: float,
    flag_pct: float,
) -> Variance:
    if field_weight_kg:
        reference, source = field_weight_kg, "field_weight"
    elif estimated_kg:
        reference, source = estimated_kg, "estimate"
    else:
        return Variance(None, None, None, None, None)
    ref = _d(reference)
    diff = _d(weighbridge_kg) - ref
    pct = (diff / ref * 100).quantize(_CENT, rounding=ROUND_HALF_UP)
    size = abs(pct)
    if size >= _d(flag_pct):
        level = LEVEL_FLAG
    elif size >= _d(warn_pct):
        level = LEVEL_WARN
    else:
        level = LEVEL_OK
    return Variance(
        reference_kg=float(ref),
        reference=source,
        variance_kg=float(diff.quantize(_TENTH, rounding=ROUND_HALF_UP)),
        variance_pct=float(pct),
        level=level,
    )


def moisture_warning(moisture_pct: float, limit_pct: float) -> str | None:
    if _d(moisture_pct) > _d(limit_pct):
        return f"Moisture {moisture_pct:g}% is above the {limit_pct:g}% limit for this crop."
    return None


def maunds(kg: float | None) -> float | None:
    """Kilograms to maunds (1 maund = 40 kg), one decimal."""
    if kg is None:
        return None
    return float((_d(kg) / KG_PER_MAUND).quantize(_TENTH, rounding=ROUND_HALF_UP))
