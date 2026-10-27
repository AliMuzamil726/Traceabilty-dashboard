"""The geometry engine: shape validation, country sanity, area, pins and overlaps."""

from __future__ import annotations

import pytest

from core.errors import ConflictError, ValidationAppError
from module_2.services import geometry as geo
from module_2.tests.conftest import LINCOLNSHIRE, MULTAN, bowtie, square


def _candidate(
    geometry: dict, *, field_id: str = "1001-01", uuid: str = "f1"
) -> geo.CandidateField:
    return geo.CandidateField(
        id=uuid,
        field_id=field_id,
        farmer_id="farmer-1",
        farmer_name="Muhammad Imran",
        sawie_id=1001,
        geometry=geometry,
    )


class TestShapeValidation:
    def test_accepts_a_plain_square(self) -> None:
        polygon, vertices = geo.parse_polygon(square(side_m=200))
        assert vertices == 4
        assert polygon.is_valid

    def test_rejects_self_intersection_without_repairing_it(self) -> None:
        with pytest.raises(ValidationAppError) as exc:
            geo.parse_polygon(bowtie())
        assert exc.value.code == "field_self_intersection"

    def test_rejects_an_unclosed_ring(self) -> None:
        ring = square()["coordinates"][0][:-1]
        with pytest.raises(ValidationAppError) as exc:
            geo.parse_polygon({"type": "Polygon", "coordinates": [ring]})
        assert "not closed" in exc.value.message

    def test_rejects_fewer_than_three_distinct_corners(self) -> None:
        a, b = [71.5, 30.1], [71.6, 30.2]
        with pytest.raises(ValidationAppError):
            geo.parse_polygon({"type": "Polygon", "coordinates": [[a, b, a]]})

    def test_rejects_holes(self) -> None:
        outer = square(side_m=400)["coordinates"][0]
        inner = square(side_m=100)["coordinates"][0]
        with pytest.raises(ValidationAppError) as exc:
            geo.parse_polygon({"type": "Polygon", "coordinates": [outer, inner]})
        assert "single ring" in exc.value.message

    @pytest.mark.parametrize(
        "payload",
        [
            None,
            "a string",
            {"type": "Point", "coordinates": [71.5, 30.1]},
            {"type": "Polygon"},
            {"type": "Polygon", "coordinates": []},
            {"type": "Polygon", "coordinates": [[[71.5], [71.6, 30.2], [71.5, 30.1]]]},
            {"type": "Polygon", "coordinates": [[["x", "y"], [1, 2], [3, 4], ["x", "y"]]]},
        ],
    )
    def test_rejects_malformed_input(self, payload: object) -> None:
        with pytest.raises(ValidationAppError):
            geo.parse_polygon(payload)

    def test_rejects_out_of_range_and_non_finite_coordinates(self) -> None:
        with pytest.raises(ValidationAppError):
            geo.parse_polygon(
                {"type": "Polygon", "coordinates": [[[200.0, 30.0], [1, 2], [3, 4], [200.0, 30.0]]]}
            )
        with pytest.raises(ValidationAppError):
            geo.parse_polygon(
                {
                    "type": "Polygon",
                    "coordinates": [[[float("inf"), 30.0], [1, 2], [3, 4], [float("inf"), 30.0]]],
                }
            )

    def test_rejects_more_than_the_vertex_limit(self) -> None:
        import math

        lat, lng = MULTAN
        count = geo.MAX_VERTICES + 5
        ring = [
            [
                lng + 0.01 * math.cos(2 * math.pi * i / count),
                lat + 0.01 * math.sin(2 * math.pi * i / count),
            ]
            for i in range(count)
        ]
        ring.append(ring[0])
        with pytest.raises(ValidationAppError) as exc:
            geo.parse_polygon({"type": "Polygon", "coordinates": [ring]})
        assert exc.value.code == "field_vertex_limit"


class TestCountryAndArea:
    def test_a_pakistani_square_is_inside_pakistan(self) -> None:
        polygon, _ = geo.parse_polygon(square(MULTAN))
        geo.check_country(polygon, "PK")

    def test_a_hemp_field_drawn_in_pakistan_is_rejected(self) -> None:
        polygon, _ = geo.parse_polygon(square(MULTAN))
        with pytest.raises(ValidationAppError) as exc:
            geo.check_country(polygon, "GB")
        assert exc.value.code == "field_outside_country"
        assert "United Kingdom" in exc.value.message

    def test_a_cotton_field_drawn_in_the_uk_is_rejected(self) -> None:
        polygon, _ = geo.parse_polygon(square(LINCOLNSHIRE))
        with pytest.raises(ValidationAppError) as exc:
            geo.check_country(polygon, "PK")
        assert exc.value.code == "field_outside_country"

    @pytest.mark.parametrize("centre", [MULTAN, LINCOLNSHIRE])
    def test_area_of_a_200_m_square_is_about_four_hectares(
        self, centre: tuple[float, float]
    ) -> None:
        polygon, _ = geo.parse_polygon(square(centre, side_m=200))
        area = geo.measure(polygon)
        assert area.m2 == pytest.approx(40_000, rel=0.01)
        assert area.ha == pytest.approx(4.0, rel=0.01)
        assert area.acre == pytest.approx(40_000 / 4046.8564224, rel=0.01)

    def test_utm_zone_follows_the_centroid(self) -> None:
        assert geo.utm_epsg(71.52, 30.15) == 32642  # Multan: zone 42 north (66E to 72E)
        assert geo.utm_epsg(-0.54, 53.23) == 32630  # Lincolnshire: zone 30 north
        assert geo.utm_epsg(-0.54, -53.23) == 32730  # same zone, southern hemisphere

    def test_rejects_a_field_below_the_minimum(self) -> None:
        polygon, _ = geo.parse_polygon(square(side_m=5))  # 25 m2
        with pytest.raises(ValidationAppError) as exc:
            geo.check_area(geo.measure(polygon))
        assert exc.value.code == "field_area_too_small"

    def test_rejects_a_field_above_the_maximum(self) -> None:
        polygon, _ = geo.parse_polygon(square(side_m=3000))  # 900 ha
        with pytest.raises(ValidationAppError) as exc:
            geo.check_area(geo.measure(polygon))
        assert exc.value.code == "field_area_too_large"


class TestPins:
    def test_defaults_to_a_point_inside_the_polygon(self) -> None:
        prepared = geo.prepare_geometry(square(), country="PK")
        polygon, _ = geo.parse_polygon(prepared.geometry)
        from shapely.geometry import Point

        assert polygon.covers(Point(prepared.pin_lng, prepared.pin_lat))

    def test_accepts_a_pin_just_outside_the_boundary(self) -> None:
        prepared = geo.prepare_geometry(
            square(side_m=200), country="PK", pin_lat=MULTAN[0] + 0.0012, pin_lng=MULTAN[1]
        )
        assert prepared.pin_lat == pytest.approx(MULTAN[0] + 0.0012)

    def test_rejects_a_pin_far_from_the_field(self) -> None:
        with pytest.raises(ValidationAppError) as exc:
            geo.prepare_geometry(
                square(side_m=200), country="PK", pin_lat=MULTAN[0] + 0.05, pin_lng=MULTAN[1]
            )
        assert exc.value.code == "field_pin_outside"


class TestOverlaps:
    def test_an_identical_polygon_is_a_full_overlap(self) -> None:
        geometry = square(side_m=200)
        polygon, _ = geo.parse_polygon(geometry)
        conflicts = geo.find_overlaps(polygon, [_candidate(geometry)])
        assert len(conflicts) == 1
        assert conflicts[0].overlap_percent_of_new_field == pytest.approx(100, rel=0.01)
        assert conflicts[0].field_code == "1001-01"

    def test_a_one_percent_overlap_is_rejected(self) -> None:
        side = 200.0
        existing = square(side_m=side)
        # Shifted east by 99 percent of the side: the shared strip is one percent.
        drawn = square(side_m=side, offset_east_m=side * 0.99)
        polygon, _ = geo.parse_polygon(drawn)
        conflicts = geo.find_overlaps(polygon, [_candidate(existing)])
        assert len(conflicts) == 1
        assert conflicts[0].overlap_percent_of_new_field == pytest.approx(1.0, abs=0.2)
        assert conflicts[0].overlap_m2 > geo.OVERLAP_TOLERANCE_M2

    def test_a_fully_contained_polygon_is_rejected(self) -> None:
        conflicts = geo.find_overlaps(
            geo.parse_polygon(square(side_m=50))[0], [_candidate(square(side_m=400))]
        )
        assert len(conflicts) == 1
        assert conflicts[0].overlap_percent_of_new_field == pytest.approx(100, rel=0.02)

    def test_fields_that_only_touch_along_an_edge_are_allowed(self) -> None:
        side = 200.0
        existing = square(side_m=side)
        neighbour = square(side_m=side, offset_east_m=side)
        polygon, _ = geo.parse_polygon(neighbour)
        assert geo.find_overlaps(polygon, [_candidate(existing)]) == []

    def test_separate_fields_do_not_conflict(self) -> None:
        polygon, _ = geo.parse_polygon(square(side_m=200, offset_east_m=1000))
        assert geo.find_overlaps(polygon, [_candidate(square(side_m=200))]) == []

    def test_a_field_being_edited_is_excluded_from_its_own_check(self) -> None:
        geometry = square(side_m=200)
        polygon, _ = geo.parse_polygon(geometry)
        candidate = _candidate(geometry, uuid="self-id")
        assert geo.find_overlaps(polygon, [candidate], exclude_field_id="self-id") == []
        assert geo.find_overlaps(polygon, [candidate], exclude_field_id="other-id")

    def test_every_conflict_is_reported_not_just_the_first(self) -> None:
        side = 200.0
        polygon, _ = geo.parse_polygon(square(side_m=side))
        candidates = [
            _candidate(square(side_m=side, offset_east_m=side * 0.5), field_id="1001-02", uuid="a"),
            _candidate(
                square(side_m=side, offset_north_m=side * 0.5), field_id="1002-01", uuid="b"
            ),
        ]
        conflicts = geo.find_overlaps(polygon, candidates)
        assert {c.field_code for c in conflicts} == {"1001-02", "1002-01"}
        # Reported worst first, so the message names the biggest problem.
        assert conflicts[0].overlap_m2 >= conflicts[1].overlap_m2

    def test_raise_for_overlaps_names_the_field_and_carries_every_reason(self) -> None:
        polygon, _ = geo.parse_polygon(square(side_m=200))
        conflicts = geo.find_overlaps(polygon, [_candidate(square(side_m=200))])
        with pytest.raises(ConflictError) as exc:
            geo.raise_for_overlaps(conflicts)
        assert exc.value.code == "field_overlap"
        assert "1001-01" in exc.value.message
        assert exc.value.details["conflicts"][0]["sawie_id"] == 1001

    def test_raise_for_overlaps_is_silent_when_there_are_none(self) -> None:
        geo.raise_for_overlaps([])

    def test_a_stored_shape_that_cannot_be_parsed_is_skipped(self) -> None:
        polygon, _ = geo.parse_polygon(square(side_m=200))
        broken = _candidate({"type": "Polygon", "coordinates": "nonsense"}, uuid="broken")
        assert geo.find_overlaps(polygon, [broken]) == []


class TestPrepareGeometry:
    def test_returns_everything_needed_to_persist_a_field(self) -> None:
        prepared = geo.prepare_geometry(square(side_m=200), country="PK")
        assert prepared.vertex_count == 4
        assert prepared.area.m2 == pytest.approx(40_000, rel=0.01)
        assert prepared.geometry["type"] == "Polygon"
        assert prepared.geometry["coordinates"][0][0] == prepared.geometry["coordinates"][0][-1]
        min_lng, min_lat, max_lng, max_lat = prepared.bbox
        assert min_lng < prepared.centroid_lng < max_lng
        assert min_lat < prepared.centroid_lat < max_lat
