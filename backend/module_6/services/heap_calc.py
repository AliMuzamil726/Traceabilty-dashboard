"""Heap and batch arithmetic. Pure functions on Decimal; no database, no rounding drift.

input_kg            = sum of weighbridge weights of delivered deliveries in the heap
expected_output_kg  = input_kg x ratio
max_bales           = floor(expected_output_kg / bale_unit_kg)
bales_made          = active bales; bales_weight_kg = their total weight
input_per_bale_kg   = bale_unit_kg / ratio
remaining_input_kg  = max(0, input_kg - bales_made x input_per_bale_kg)
remaining_output_kg = remaining_input_kg x ratio
can_close           = remaining_output_kg < bale_unit_kg
Hemp also: expected shiv and dust = input_kg x their percentages.
Cotton also: seed cotton in maunds = input_kg / 40.

Weights are reported to 0.01 kg (half up). ``max_bales`` and ``can_close`` are decided
on the unrounded values, so rounding can never allow an extra bale.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal

KG_PER_MAUND = Decimal(40)
CENT = Decimal("0.01")
HUNDRED = Decimal(100)


def D(value: float | int | str | Decimal | None) -> Decimal:  # noqa: N802 - reads as a cast
    if value is None:
        return Decimal(0)
    return value if isinstance(value, Decimal) else Decimal(str(value))


def kg(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class HeapTotals:
    input_kg: Decimal
    input_maunds: Decimal | None
    outturn_ratio_pct: Decimal
    bale_unit_kg: Decimal
    expected_output_kg: Decimal
    max_bales: int
    bales_made: int
    bales_weight_kg: Decimal
    input_per_bale_kg: Decimal
    remaining_input_kg: Decimal
    remaining_output_kg: Decimal
    consumed_pct: Decimal
    can_close: bool
    can_add_bales: int
    expected_shiv_kg: Decimal | None
    expected_dust_kg: Decimal | None


def totals(
    *,
    crop: str,
    weighbridge_kg: Iterable[float | Decimal | None],
    outturn_ratio_pct: float | Decimal,
    bale_unit_kg: float | Decimal,
    active_bale_weights: Sequence[float | Decimal],
    shiv_pct: float | Decimal | None = None,
    dust_pct: float | Decimal | None = None,
) -> HeapTotals:
    ratio = D(outturn_ratio_pct) / HUNDRED
    unit = D(bale_unit_kg)
    if ratio <= 0 or unit <= 0:
        raise ValueError("The outturn ratio and the bale unit must be positive.")
    input_kg = sum((D(w) for w in weighbridge_kg), Decimal(0))
    expected = input_kg * ratio
    max_bales = int((expected / unit).to_integral_value(rounding=ROUND_DOWN))
    made = len(active_bale_weights)
    bales_weight = sum((D(w) for w in active_bale_weights), Decimal(0))
    per_bale = unit / ratio
    remaining_input = max(Decimal(0), input_kg - made * per_bale)
    remaining_output = remaining_input * ratio
    consumed = (
        Decimal(0)
        if input_kg == 0
        else min(HUNDRED, (input_kg - remaining_input) / input_kg * HUNDRED)
    )
    hemp = crop == "hemp"
    return HeapTotals(
        input_kg=kg(input_kg),
        input_maunds=kg(input_kg / KG_PER_MAUND) if crop == "cotton" else None,
        outturn_ratio_pct=D(outturn_ratio_pct),
        bale_unit_kg=kg(unit),
        expected_output_kg=kg(expected),
        max_bales=max_bales,
        bales_made=made,
        bales_weight_kg=kg(bales_weight),
        input_per_bale_kg=kg(per_bale),
        remaining_input_kg=kg(remaining_input),
        remaining_output_kg=kg(remaining_output),
        consumed_pct=kg(consumed),
        can_close=remaining_output < unit,
        can_add_bales=max(0, max_bales - made),
        expected_shiv_kg=kg(input_kg * D(shiv_pct) / HUNDRED)
        if hemp and shiv_pct is not None
        else None,
        expected_dust_kg=kg(input_kg * D(dust_pct) / HUNDRED)
        if hemp and dust_pct is not None
        else None,
    )


def mass_balance_ok(t: HeapTotals, extra_bales_kg: Decimal = Decimal(0)) -> bool:
    """Total bale weight may never exceed expected output."""
    return t.bales_weight_kg + extra_bales_kg <= t.expected_output_kg


@dataclass(frozen=True)
class Contribution:
    farmer_id: str
    kg: Decimal
    pct: Decimal
    deliveries: int
    fields: int


def contributions(rows: Iterable[tuple[str, str, float | Decimal | None]]) -> list[Contribution]:
    """Per farmer share of the heap input. ``rows`` are (farmer_id, field_id, kg).

    Percentages are rounded to 0.01 with the largest-remainder method, so they always
    add up to exactly 100.00 when there is any input. Sorted by weight, largest first.
    """
    per: dict[str, tuple[Decimal, int, set[str]]] = {}
    for farmer_id, field_id, weight in rows:
        total, count, fields = per.get(farmer_id, (Decimal(0), 0, set()))
        fields.add(field_id)
        per[farmer_id] = (total + D(weight), count + 1, fields)
    grand = sum((v[0] for v in per.values()), Decimal(0))
    if grand == 0:
        return [Contribution(f, kg(v[0]), Decimal("0.00"), v[1], len(v[2])) for f, v in per.items()]
    raw = {f: v[0] / grand * HUNDRED for f, v in per.items()}
    floors = {f: r.quantize(CENT, rounding=ROUND_DOWN) for f, r in raw.items()}
    short = int(((HUNDRED - sum(floors.values())) / CENT).to_integral_value(rounding=ROUND_HALF_UP))
    for f in sorted(raw, key=lambda f: (raw[f] - floors[f], per[f][0]), reverse=True)[:short]:
        floors[f] += CENT
    out = [Contribution(f, kg(v[0]), floors[f], v[1], len(v[2])) for f, v in per.items()]
    return sorted(out, key=lambda c: (-c.kg, c.farmer_id))
