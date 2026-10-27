"""Every heap formula with exact numbers."""

from __future__ import annotations

from decimal import Decimal

import pytest

from module_6.services.heap_calc import contributions, mass_balance_ok, totals

D = Decimal


def cotton(weights: list[float], bales: int = 0, ratio: float = 34, unit: float = 170):
    return totals(
        crop="cotton",
        weighbridge_kg=weights,
        outturn_ratio_pct=ratio,
        bale_unit_kg=unit,
        active_bale_weights=[unit] * bales,
    )


def test_the_documented_example() -> None:
    t = cotton([8000, 5000, 4000])  # 17,000 kg of seed cotton
    assert t.input_kg == D("17000.00")
    assert t.input_maunds == D("425.00")
    assert t.expected_output_kg == D("5780.00")
    assert t.max_bales == 34
    assert t.input_per_bale_kg == D("500.00")
    assert t.remaining_input_kg == D("17000.00")
    assert t.remaining_output_kg == D("5780.00")
    assert t.can_close is False
    assert t.can_add_bales == 34


def test_bales_consume_input() -> None:
    t = cotton([17000], bales=10)
    assert t.bales_made == 10
    assert t.bales_weight_kg == D("1700.00")
    assert t.remaining_input_kg == D("12000.00")  # 17,000 - 10 x 500
    assert t.remaining_output_kg == D("4080.00")
    assert t.consumed_pct == D("29.41")
    assert t.can_add_bales == 24


def test_full_heap_can_close() -> None:
    t = cotton([17000], bales=34)
    assert t.remaining_input_kg == D("0.00")
    assert t.remaining_output_kg == D("0.00")
    assert t.can_close is True
    assert t.can_add_bales == 0
    assert mass_balance_ok(t)
    assert not mass_balance_ok(t, D(170))


def test_remainder_below_one_bale_can_close() -> None:
    t = cotton([17400], bales=34)  # 5,916 kg expected; 34 bales use 17,000 kg of input
    assert t.max_bales == 34
    assert t.remaining_input_kg == D("400.00")
    assert t.remaining_output_kg == D("136.00")
    assert t.can_close is True


def test_rounding_never_allows_an_extra_bale() -> None:
    t = cotton([499.99])  # 169.9966 kg expected, which would round to 170.00
    assert t.expected_output_kg == D("170.00")
    assert t.max_bales == 0
    assert t.can_close is True
    third = totals(
        crop="cotton",
        weighbridge_kg=[1000],
        outturn_ratio_pct=D("33.333"),
        bale_unit_kg=100,
        active_bale_weights=[],
    )
    assert third.expected_output_kg == D("333.33")
    assert third.max_bales == 3
    assert third.input_per_bale_kg == D("300.00")


def test_hemp_shiv_and_dust() -> None:
    t = totals(
        crop="hemp",
        weighbridge_kg=[10000, 2000],
        outturn_ratio_pct=25,
        bale_unit_kg=250,
        active_bale_weights=[250, 250],
        shiv_pct=55,
        dust_pct=15,
    )
    assert t.expected_output_kg == D("3000.00")
    assert t.max_bales == 12
    assert t.expected_shiv_kg == D("6600.00")
    assert t.expected_dust_kg == D("1800.00")
    assert t.input_maunds is None
    assert t.input_per_bale_kg == D("1000.00")
    assert t.remaining_input_kg == D("10000.00")


def test_empty_heap() -> None:
    t = cotton([])
    assert (t.input_kg, t.max_bales, t.consumed_pct, t.can_close) == (D("0.00"), 0, D("0.00"), True)


def test_bad_configuration_is_refused() -> None:
    with pytest.raises(ValueError, match="must be positive"):
        cotton([100], ratio=0)


def test_contributions_sum_to_exactly_100() -> None:
    rows = [("a", "f1", 1000), ("b", "f2", 1000), ("c", "f3", 1000), ("a", "f4", 500)]
    out = contributions(rows)
    assert [c.farmer_id for c in out] == ["a", "b", "c"]
    assert sum(c.pct for c in out) == D("100.00")
    a = out[0]
    assert (a.kg, a.pct, a.deliveries, a.fields) == (D("1500.00"), D("42.86"), 2, 2)
    thirds = contributions([("x", "f", 1), ("y", "g", 1), ("z", "h", 1)])
    assert sum(c.pct for c in thirds) == D("100.00")
    assert sorted(c.pct for c in thirds) == [D("33.33"), D("33.33"), D("33.34")]
    assert contributions([]) == []
