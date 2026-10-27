"""Per-crop constants for Radar. The crop clock is not here: it belongs to Module 3."""

from __future__ import annotations

#: Used only when a fieldbook has no yield yet, and always shown as an estimate.
#: Cotton: about 20 maunds of seed cotton per acre (800 kg). Hemp: about 6 t of straw per ha.
BENCHMARK_KG = {"cotton": (800.0, "acre"), "hemp": (6000.0, "ha")}

#: The area unit shown first for each crop; the other is shown muted beside it.
AREA_UNIT = {"cotton": "acre", "hemp": "ha"}

#: "Approaching within N days" in the KPI strip.
APPROACHING_WINDOW_DAYS = 14

#: Map and export caps.
MAP_FEATURE_LIMIT = 2000
