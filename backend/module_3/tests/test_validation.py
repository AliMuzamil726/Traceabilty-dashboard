"""The form engine: every field type, ranges, visibility, computed values and rules."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import pytest

from module_3.services import formschema as fs
from module_3.tests.conftest import cotton_steps, hemp_steps

TODAY = date(2026, 10, 21)


def ctx(**over: Any) -> fs.ValidationContext:
    """A context whose option lists accept the values the fixtures use."""
    allowed = {
        "crop_season": {"kharif", "rabi"},
        "soil_texture": {"loam"},
        "drainage_status": {"well_drained"},
        "machinery_type": {"tractor_owned", "bullock_drawn", "manual"},
        "operation_type_cotton": {"deep_ploughing"},
        "residue_handling": {"incorporated"},
        "cover_crop": {"none"},
        "irrigation_source": {"canal", "tubewell_diesel", "tubewell_electric", "tubewell_solar"},
        "irrigation_method": {"furrow", "drip"},
        "weed_method": {"manual_weeding", "chemical", "mixed"},
        "spraying_implement": {"boom_sprayer"},
        "beneficial_insects": {"lacewing", "spiders"},
        "pest_product_type": {"insecticide"},
        "picking_number": {"1st", "2nd"},
        "harvest_method_cotton": {"manual_picking"},
        "storage_material": {"cotton_cloth", "polypropylene_not_recommended"},
        "yes_no": {"yes", "no"},
        "fertiliser_product_cotton": {"urea"},
        "nutrient_crop_stage": {"seedling"},
    }
    base = fs.ValidationContext(
        today=TODAY,
        options=lambda key: allowed.get(key, set()),
        values={"field.area_acre": 10.0, "field.area_ha": 4.0},
        sowing_ref="step.sowing.sowing_date",
    )
    for key, value in over.items():
        setattr(base, key, value)
    return base


def step(crop: str, key: str) -> dict[str, Any]:
    return fs.get_step(fs.load_definition(crop), key)


def errors(result: fs.EntryResult) -> dict[str, str]:
    return {i.field: i.message for i in result.errors}


def warnings(result: fs.EntryResult) -> set[str]:
    return {i.field for i in result.warnings}


# ------------------------------------------------------------------ field types


class TestTypes:
    def test_required_fields_are_reported_by_name(self) -> None:
        result = fs.validate_entry(step("cotton", "energy"), {}, ctx())
        assert set(errors(result)) == {"total_diesel", "grid_electricity"}
        assert errors(result)["total_diesel"] == "Total field diesel is required."

    def test_numbers_are_coerced_and_bounded(self) -> None:
        s = step("cotton", "energy")
        ok = fs.validate_entry(s, {"total_diesel": "120.5", "grid_electricity": 0}, ctx())
        assert ok.ok
        assert ok.clean["total_diesel"] == 120.5
        assert "total_diesel" in errors(
            fs.validate_entry(s, {"total_diesel": -1, "grid_electricity": 0}, ctx())
        )
        assert "total_diesel" in errors(
            fs.validate_entry(s, {"total_diesel": 10**9, "grid_electricity": 0}, ctx())
        )
        assert "total_diesel" in errors(
            fs.validate_entry(s, {"total_diesel": "lots", "grid_electricity": 0}, ctx())
        )
        assert "total_diesel" in errors(
            fs.validate_entry(s, {"total_diesel": True, "grid_electricity": 0}, ctx())
        )

    def test_integers_reject_fractions(self) -> None:
        data = dict(cotton_steps()["land_preparation"][0], passes=1.5)
        result = fs.validate_entry(step("cotton", "land_preparation"), data, ctx())
        assert errors(result)["passes"] == "Number of passes must be a whole number."

    @pytest.mark.parametrize(("passes", "ok"), [(0, False), (1, True), (12, True), (13, False)])
    def test_passes_range_is_1_to_12(self, passes: int, ok: bool) -> None:
        data = dict(
            cotton_steps()["land_preparation"][0], passes=passes, operation_date="2026-01-01"
        )
        result = fs.validate_entry(step("cotton", "land_preparation"), data, ctx())
        assert ("passes" not in errors(result)) is ok

    def test_dates_must_be_iso_and_not_in_the_future(self) -> None:
        s = step("cotton", "weed_management")
        assert errors(
            fs.validate_entry(s, {"weed_date": "21/10/2026", "method": "manual_weeding"}, ctx())
        )
        future = (TODAY + timedelta(days=1)).isoformat()
        r = fs.validate_entry(s, {"weed_date": future, "method": "manual_weeding"}, ctx())
        assert errors(r)["weed_date"] == "Date cannot be in the future."
        assert fs.validate_entry(
            s, {"weed_date": TODAY.isoformat(), "method": "manual_weeding"}, ctx()
        ).ok

    def test_a_date_marked_not_future_false_may_be_in_the_future(self) -> None:
        data = dict(hemp_steps()["field_info"], licence_expiry="2030-01-01")
        result = fs.validate_entry(
            step("hemp", "field_info"),
            data,
            ctx(
                options=lambda key: {"spring_sowing", "clay_loam", "winter_wheat"},
                values={"field.area_ha": 4.0, "farmer.licence": "HO-1"},
            ),
        )
        assert result.ok, errors(result)

    def test_selects_accept_only_list_values(self) -> None:
        s = step("cotton", "transport")
        r = fs.validate_entry(s, {"transport_distance": 10, "transport_mode": "rocket"}, ctx())
        assert errors(r)["transport_mode"] == "Choose a transport mode from the list."

    def test_multiselect_checks_each_value_and_drops_duplicates(self) -> None:
        s = step("cotton", "pest_disease")
        base = {"product_applied": "X", "product_type": "insecticide"}
        r = fs.validate_entry(
            s, {**base, "beneficial_insects": ["lacewing", "lacewing", "spiders"]}, ctx()
        )
        assert r.clean["beneficial_insects"] == ["lacewing", "spiders"]
        assert errors(fs.validate_entry(s, {**base, "beneficial_insects": ["dragons"]}, ctx()))
        assert errors(fs.validate_entry(s, {**base, "beneficial_insects": "lacewing"}, ctx()))

    def test_yesno_uses_its_list(self) -> None:
        s = step("cotton", "labour_social")
        base = {"family_labour": 1, "hired_labour": 1, "women_pickers": 1, "picking_wage": 10}
        assert fs.validate_entry(s, {**base, "training_attended": "no"}, ctx()).ok
        assert errors(fs.validate_entry(s, {**base, "training_attended": "maybe"}, ctx()))

    def test_paired_numbers_validate_each_part(self) -> None:
        s = step("cotton", "nutrient_management")
        base = dict(cotton_steps()["nutrient_management"][0], application_date="2026-06-01")
        ok = fs.validate_entry(s, {**base, "pk_content": {"p2o5": 46, "k2o": 0}}, ctx())
        assert ok.clean["pk_content"] == {"p2o5": 46.0, "k2o": 0.0}
        bad = fs.validate_entry(s, {**base, "pk_content": {"p2o5": 146}}, ctx())
        assert "pk_content.p2o5" in errors(bad)
        assert errors(fs.validate_entry(s, {**base, "pk_content": 5}, ctx()))

    def test_dates_list_is_sorted_deduplicated_and_checked(self) -> None:
        s = step("hemp", "retting")
        base = {"retting_start": "2026-09-01", "retting_end": "2026-09-20", "location": "Field"}
        r = fs.validate_entry(
            s, {**base, "turning_dates": ["2026-09-10", "2026-09-05", "2026-09-10"]}, ctx()
        )
        assert r.clean["turning_dates"] == ["2026-09-05", "2026-09-10"]
        assert errors(fs.validate_entry(s, {**base, "turning_dates": ["soon"]}, ctx()))
        assert errors(fs.validate_entry(s, {**base, "turning_dates": ["2099-01-01"]}, ctx()))

    def test_text_is_trimmed_and_length_capped(self) -> None:
        s = step("hemp", "weeds_pests")
        base = {"issue_date": "2026-07-01", "severity": "low"}
        opts = ctx(options=lambda key: {"low"})
        assert (
            fs.validate_entry(s, {**base, "issue": "  Fat   hen "}, opts).clean["issue"]
            == "Fat hen"
        )
        assert errors(fs.validate_entry(s, {**base, "issue": "x" * 501}, opts))

    def test_unknown_keys_are_dropped(self) -> None:
        r = fs.validate_entry(
            step("cotton", "energy"),
            {"total_diesel": 1, "grid_electricity": 1, "secret": "x"},
            ctx(),
        )
        assert "secret" not in r.clean


# ------------------------------------------------------------------ visibility


class TestVisibility:
    def test_diesel_per_pass_is_hidden_for_bullock_and_manual(self) -> None:
        s = step("cotton", "land_preparation")
        base = dict(cotton_steps()["land_preparation"][0], operation_date="2026-01-01")
        for hidden in ("bullock_drawn", "manual"):
            r = fs.validate_entry(
                s, {**base, "machinery_type": hidden, "diesel_per_pass": 99}, ctx()
            )
            # Hidden fields are neither validated (99 is above the max) nor stored.
            assert r.ok, errors(r)
            assert "diesel_per_pass" not in r.clean
        shown = fs.validate_entry(
            s, {**base, "machinery_type": "tractor_owned", "diesel_per_pass": 99}, ctx()
        )
        assert "diesel_per_pass" in errors(shown)

    @pytest.mark.parametrize(
        ("source", "method", "visible"),
        [
            ("canal", "furrow", set()),
            ("tubewell_diesel", "furrow", {"diesel_used", "pumping_head", "pump_efficiency"}),
            (
                "tubewell_electric",
                "furrow",
                {"electricity_used", "pumping_head", "pump_efficiency"},
            ),
            ("tubewell_solar", "furrow", {"pumping_head", "pump_efficiency"}),
            ("canal", "drip", {"drip_area"}),
        ],
    )
    def test_irrigation_energy_fields_follow_source_and_method(
        self, source: str, method: str, visible: set[str]
    ) -> None:
        conditional = {
            "diesel_used",
            "electricity_used",
            "pumping_head",
            "pump_efficiency",
            "drip_area",
        }
        data = {
            "irrigation_date": "2026-06-01",
            "source": source,
            "method": method,
            "duration": 2,
            "water_applied": 50,
            **dict.fromkeys(conditional, 1),
        }
        r = fs.validate_entry(step("cotton", "irrigation"), data, ctx())
        assert r.ok, errors(r)
        assert set(r.clean) & conditional == visible

    def test_chemical_weed_fields_appear_for_chemical_and_mixed(self) -> None:
        s = step("cotton", "weed_management")
        base = {"weed_date": "2026-06-01"}
        manual = fs.validate_entry(
            s, {**base, "method": "manual_weeding", "chemical_product": "X"}, ctx()
        )
        assert "chemical_product" not in manual.clean
        # Chemical product is required once it is visible.
        chemical = fs.validate_entry(s, {**base, "method": "chemical"}, ctx())
        assert "chemical_product" in errors(chemical)

    def test_training_name_is_required_only_when_training_was_attended(self) -> None:
        s = step("cotton", "labour_social")
        base = {"family_labour": 1, "hired_labour": 1, "women_pickers": 1, "picking_wage": 10}
        assert fs.validate_entry(s, {**base, "training_attended": "no"}, ctx()).ok
        assert "training_name" in errors(
            fs.validate_entry(s, {**base, "training_attended": "yes"}, ctx())
        )

    def test_is_visible_helper(self) -> None:
        f = {"visible_if": {"field": "m", "not_in": ["a"]}}
        assert fs.is_visible(f, {})  # unanswered controls hide nothing
        assert not fs.is_visible(f, {"m": "a"})
        assert fs.is_visible({"visible_if": {"field": "m", "in": ["b"]}}, {"m": "b"})


# ------------------------------------------------------------------- computed


class TestComputed:
    def test_turn_count_and_days_in_swath(self) -> None:
        r = fs.validate_entry(
            step("hemp", "retting"),
            {
                "retting_start": "2026-09-01",
                "turning_dates": ["2026-09-05", "2026-09-10", "2026-09-15"],
                "retting_end": "2026-09-21",
                "location": "Field",
                "number_of_turns": 99,
                "days_in_swath": 99,  # client values are ignored
            },
            ctx(),
        )
        assert r.clean["number_of_turns"] == 3
        assert r.clean["days_in_swath"] == 20

    def test_no_turning_dates_counts_zero(self) -> None:
        r = fs.validate_entry(
            step("hemp", "retting"),
            {"retting_start": "2026-09-01", "retting_end": "2026-09-01", "location": "Field"},
            ctx(),
        )
        assert r.clean["number_of_turns"] == 0
        assert r.clean["days_in_swath"] == 0

    def test_total_straw_weight_is_bales_times_average(self) -> None:
        data = dict(hemp_steps()["baling"][0], baling_date="2026-10-01", total_straw_weight=1)
        r = fs.validate_entry(
            step("hemp", "baling"), data, ctx(options=lambda key: {"large_square", "yes", "no"})
        )
        assert r.clean["total_straw_weight"] == 20 * 450


# ---------------------------------------------------------------------- rules


class TestRules:
    def test_area_sown_may_exceed_the_field_by_5_percent_only(self) -> None:
        s = step("cotton", "field_info")
        base = cotton_steps()["field_info"]
        assert fs.validate_entry(s, {**base, "area_sown": 10.5}, ctx()).ok
        r = fs.validate_entry(s, {**base, "area_sown": 10.51}, ctx())
        assert "5 percent" in errors(r)["area_sown"]

    def test_women_pickers_cannot_exceed_family_plus_hired(self) -> None:
        s = step("cotton", "labour_social")
        base = {"family_labour": 2, "hired_labour": 3, "picking_wage": 1, "training_attended": "no"}
        assert fs.validate_entry(s, {**base, "women_pickers": 5}, ctx()).ok
        assert "women_pickers" in errors(fs.validate_entry(s, {**base, "women_pickers": 6}, ctx()))

    def test_picking_numbers_are_unique_within_the_book(self) -> None:
        s = step("cotton", "harvest")
        data = dict(cotton_steps()["harvest"][0], picking_date="2026-10-01")
        clash = ctx(sibling_entries=[{"picking_number": "1st"}])
        assert "picking_number" in errors(fs.validate_entry(s, data, clash))
        assert fs.validate_entry(s, {**data, "picking_number": "2nd"}, clash).ok

    def test_harvest_must_be_after_sowing(self) -> None:
        s = step("cotton", "harvest")
        sown = ctx(single_steps={"sowing": {"sowing_date": "2026-06-01"}})
        data = dict(cotton_steps()["harvest"][0])
        assert "picking_date" in errors(
            fs.validate_entry(s, {**data, "picking_date": "2026-06-01"}, sown)
        )
        assert fs.validate_entry(s, {**data, "picking_date": "2026-06-02"}, sown).ok

    def test_land_preparation_after_sowing_is_only_a_warning(self) -> None:
        s = step("cotton", "land_preparation")
        sown = ctx(single_steps={"sowing": {"sowing_date": "2026-06-01"}})
        r = fs.validate_entry(
            s, dict(cotton_steps()["land_preparation"][0], operation_date="2026-06-05"), sown
        )
        assert r.ok
        assert "operation_date" in warnings(r)

    def test_irrigation_more_than_30_days_before_sowing_warns(self) -> None:
        s = step("cotton", "irrigation")
        sown = ctx(single_steps={"sowing": {"sowing_date": "2026-06-01"}})
        base = {"source": "canal", "method": "furrow", "duration": 1, "water_applied": 10}
        assert not warnings(fs.validate_entry(s, {**base, "irrigation_date": "2026-05-02"}, sown))
        assert "irrigation_date" in warnings(
            fs.validate_entry(s, {**base, "irrigation_date": "2026-05-01"}, sown)
        )

    def test_area_covered_above_area_sown_times_passes_warns(self) -> None:
        s = step("cotton", "land_preparation")
        sown = ctx(single_steps={"field_info": {"area_sown": 5}})
        base = dict(cotton_steps()["land_preparation"][0], operation_date="2026-01-01", passes=2)
        assert not warnings(fs.validate_entry(s, {**base, "area_covered": 10}, sown))
        assert "area_covered" in warnings(
            fs.validate_entry(s, {**base, "area_covered": 10.5}, sown)
        )

    def test_rules_without_their_reference_are_skipped(self) -> None:
        # No sowing date yet: date rules cannot be judged, so they do not fire.
        r = fs.validate_entry(step("cotton", "harvest"), dict(cotton_steps()["harvest"][0]), ctx())
        assert r.ok

    def test_retting_end_must_not_precede_the_start(self) -> None:
        s = step("hemp", "retting")
        r = fs.validate_entry(
            s,
            {"retting_start": "2026-09-10", "retting_end": "2026-09-09", "location": "Field"},
            ctx(),
        )
        assert "retting_end" in errors(r)

    def test_area_cut_cannot_exceed_area_drilled(self) -> None:
        s = step("hemp", "harvest")
        drilled = ctx(
            single_steps={"field_info": {"area_drilled": 3}},
            options=lambda key: {"early_flowering", "mower_conditioner"},
        )
        base = dict(hemp_steps()["harvest"], cutting_date="2026-09-01")
        assert fs.validate_entry(s, {**base, "area_cut": 3}, drilled).ok
        assert "area_cut" in errors(fs.validate_entry(s, {**base, "area_cut": 3.01}, drilled))

    def test_licence_expiring_before_drilling_warns(self) -> None:
        s = step("hemp", "field_info")
        c = ctx(
            single_steps={"sowing": {"drilling_date": "2026-05-01"}},
            options=lambda key: {"spring_sowing", "clay_loam", "winter_wheat"},
            values={"field.area_ha": 4.0},
        )
        base = dict(hemp_steps()["field_info"])
        assert "licence_expiry" in warnings(
            fs.validate_entry(s, {**base, "licence_expiry": "2026-04-30"}, c)
        )
        assert not warnings(fs.validate_entry(s, {**base, "licence_expiry": "2026-05-01"}, c))

    def test_field_warnings_for_moisture_and_polypropylene(self) -> None:
        s = step("cotton", "harvest")
        base = dict(cotton_steps()["harvest"][0])
        assert not warnings(fs.validate_entry(s, {**base, "moisture": 12}, ctx()))
        assert "moisture" in warnings(fs.validate_entry(s, {**base, "moisture": 12.1}, ctx()))
        r = fs.validate_entry(
            s, {**base, "storage_material": "polypropylene_not_recommended"}, ctx()
        )
        assert r.ok
        assert "storage_material" in warnings(r)

    def test_readonly_defaults_take_the_server_value(self) -> None:
        s = step("hemp", "field_info")
        c = ctx(
            options=lambda key: {"spring_sowing", "clay_loam", "winter_wheat"},
            values={"field.area_ha": 4.0, "farmer.licence": "HO-REAL"},
        )
        r = fs.validate_entry(s, {**hemp_steps()["field_info"], "licence_no": "FORGED"}, c)
        assert r.clean["licence_no"] == "HO-REAL"


def test_summary_uses_labels_not_codes() -> None:
    s = step("cotton", "harvest")
    text = fs.summarise(
        s,
        {"picking_number": "1st", "picking_date": "2026-10-01", "yield": 12.0},
        lambda key, value: {"1st": "1st"}.get(value, value.upper()),
    )
    assert text == "1st picking on 2026-10-01, 12 maunds per acre"
    assert fs.summarise(s, {}, lambda k, v: v) == "- picking on -, - maunds per acre"
