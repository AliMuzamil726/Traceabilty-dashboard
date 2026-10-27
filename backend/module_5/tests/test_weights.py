"""Variance maths and moisture warnings, at the thresholds, for both crops."""

from __future__ import annotations

import pytest

from module_5.seed import DEFAULT_CONFIG
from module_5.services.weights import maunds, moisture_warning, variance


@pytest.mark.parametrize("crop", ["cotton", "hemp"])
@pytest.mark.parametrize(
    ("weighbridge", "pct", "level"),
    [
        (1029.9, 2.99, "ok"),
        (1030.0, 3.0, "warn"),
        (1049.9, 4.99, "warn"),
        (1050.0, 5.0, "flag"),
        (970.1, -2.99, "ok"),
        (970.0, -3.0, "warn"),
        (950.0, -5.0, "flag"),
        (1000.0, 0.0, "ok"),
    ],
)
def test_variance_levels(crop: str, weighbridge: float, pct: float, level: str) -> None:
    warn, flag, _ = DEFAULT_CONFIG[crop]
    v = variance(weighbridge, field_weight_kg=1000, estimated_kg=None, warn_pct=warn, flag_pct=flag)
    assert (v.variance_pct, v.level, v.reference) == (pct, level, "field_weight")
    assert v.variance_kg == round(weighbridge - 1000, 1)


def test_field_weight_wins_over_the_estimate() -> None:
    v = variance(1000, field_weight_kg=990, estimated_kg=2000, warn_pct=3, flag_pct=5)
    assert (v.reference_kg, v.variance_kg, v.variance_pct, v.level) == (990, 10, 1.01, "ok")
    e = variance(1000, field_weight_kg=None, estimated_kg=800, warn_pct=3, flag_pct=5)
    assert (e.reference, e.variance_pct, e.level) == ("estimate", 25.0, "flag")


def test_no_reference_means_no_variance() -> None:
    v = variance(1000, field_weight_kg=None, estimated_kg=None, warn_pct=3, flag_pct=5)
    assert (v.variance_kg, v.variance_pct, v.level) == (None, None, None)


def test_moisture_limits_per_crop() -> None:
    cotton, hemp = DEFAULT_CONFIG["cotton"][2], DEFAULT_CONFIG["hemp"][2]
    assert (cotton, hemp) == (12.0, 16.0)
    assert moisture_warning(12, cotton) is None
    assert moisture_warning(12.1, cotton) == "Moisture 12.1% is above the 12% limit for this crop."
    assert moisture_warning(15, hemp) is None
    assert moisture_warning(16.5, hemp) is not None


def test_maunds() -> None:
    assert maunds(400) == 10.0
    assert maunds(1001) == 25.0
    assert maunds(None) is None
