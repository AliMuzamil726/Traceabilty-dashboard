"""Authoritative geometry engine for field boundaries.

The client draws on a map, but nothing it sends is trusted: every polygon is
re-validated here, every area is recomputed here, and the zero-overlap rule is
enforced here, including a second time inside the saving transaction.

Rules, in the order they are applied:

1. **Shape** - a single-ring GeoJSON Polygon in WGS84, closed, at least three
   distinct vertices, at most :data:`MAX_VERTICES`, finite coordinates in range,
   and not self-intersecting. Invalid shapes are rejected, never repaired.
2. **Country** - the polygon must sit inside a generous box around the farmer's
   country, so a hemp field cannot be drawn in Pakistan.
3. **Area** - computed in a local metric CRS (the UTM zone of the centroid), then
   converted to acres and hectares. Must be between :data:`MIN_AREA_M2` and
   :data:`MAX_AREA_M2`.
4. **Overlap** - zero tolerance. Any intersection larger than
   :data:`OVERLAP_TOLERANCE_M2` with any other active field, including another
   field of the same farmer, is rejected. Polygons that only touch along a shared
   boundary intersect in zero area and are allowed.

Areas and overlaps are measured in metres, never in degrees: a degree of longitude
is about 91 km in Multan and about 62 km in Lincolnshire, so degree-based areas
would be wrong by a different amount in each programme.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from pyproj import CRS, Transformer
from shapely.geometry import Polygon, shape
from shapely.geometry.base import BaseGeometry
from shapely.ops import transform as shapely_transform
from shapely.strtree import STRtree
from shapely.validation import explain_validity

from core import app_settings
from core.errors import ConflictError, ValidationAppError
from module_2.models import COUNTRY_GB, COUNTRY_PK

#: 1 acre in square metres (international acre, as used in DATA_MODEL.md).
M2_PER_ACRE = 4046.8564224
M2_PER_HECTARE = 10_000.0

MIN_VERTICES = 3
MAX_VERTICES = 500

# Defaults; the values in force come from Settings (``validation.field_*_area_m2``).
MIN_AREA_M2 = 100.0
MAX_AREA_M2 = 500 * M2_PER_HECTARE  # 500 hectares


def area_limits() -> tuple[float, float]:
    """The smallest and largest mapped field area allowed, as configured."""
    return (
        float(app_settings.setting_or("validation.field_min_area_m2", MIN_AREA_M2)),
        float(app_settings.setting_or("validation.field_max_area_m2", MAX_AREA_M2)),
    )


#: Intersections at or below this are numerical noise from floating point, not
#: real overlap. Anything above it is a conflict, however small a share it is.
OVERLAP_TOLERANCE_M2 = 0.01

#: A pin may sit just outside a boundary (a gate or a track), but not far outside.
PIN_MAX_DISTANCE_M = 50.0

#: Generous country boxes: (min_lng, min_lat, max_lng, max_lat).
COUNTRY_BBOX: dict[str, tuple[float, float, float, float]] = {
    COUNTRY_PK: (60.0, 23.0, 78.5, 37.5),
    COUNTRY_GB: (-9.0, 49.3, 2.2, 61.2),
}

COUNTRY_LABEL: dict[str, str] = {COUNTRY_PK: "Pakistan", COUNTRY_GB: "the United Kingdom"}


def _invalid(
    message: str, code: str = "field_geometry_invalid", **details: Any
) -> ValidationAppError:
    return ValidationAppError(message, code=code, details=details or None)


@dataclass(frozen=True)
class AreaResult:
    """One area in the three units the product uses."""

    m2: float
    acre: float
    ha: float


@dataclass(frozen=True)
class GeometryResult:
    """Everything derived from a validated polygon, ready to persist."""

    geometry: dict[str, Any]
    area: AreaResult
    vertex_count: int
    bbox_min_lng: float
    bbox_min_lat: float
    bbox_max_lng: float
    bbox_max_lat: float
    centroid_lat: float
    centroid_lng: float
    pin_lat: float
    pin_lng: float

    @property
    def bbox(self) -> tuple[float, float, float, float]:
        return (self.bbox_min_lng, self.bbox_min_lat, self.bbox_max_lng, self.bbox_max_lat)


@dataclass(frozen=True)
class OverlapConflict:
    """One existing field that the new polygon overlaps."""

    field_id: str
    field_code: str
    farmer_id: str
    farmer_name: str
    sawie_id: int
    overlap_m2: float
    overlap_percent_of_new_field: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "field_id": self.field_id,
            "field_code": self.field_code,
            "farmer_id": self.farmer_id,
            "farmer_name": self.farmer_name,
            "sawie_id": self.sawie_id,
            "overlap_m2": round(self.overlap_m2, 2),
            "overlap_percent_of_new_field": round(self.overlap_percent_of_new_field, 4),
        }


@dataclass(frozen=True)
class CandidateField:
    """An existing field to test against, as supplied by the repository."""

    id: str
    field_id: str
    farmer_id: str
    farmer_name: str
    sawie_id: int
    geometry: dict[str, Any]


# --------------------------------------------------------------- projection helpers


def utm_epsg(lng: float, lat: float) -> int:
    """EPSG code of the UTM zone containing ``(lng, lat)``."""
    zone = math.floor((lng + 180.0) / 6.0) + 1
    zone = min(max(zone, 1), 60)
    return (32600 if lat >= 0 else 32700) + zone


@lru_cache(maxsize=64)
def _transformer(epsg: int) -> Transformer:
    """Cached WGS84 to metric transformer (building one is comparatively slow)."""
    return Transformer.from_crs(CRS.from_epsg(4326), CRS.from_epsg(epsg), always_xy=True)


def project(geom: BaseGeometry, epsg: int) -> BaseGeometry:
    """Project a lon/lat geometry into the metric CRS ``epsg``."""
    return shapely_transform(_transformer(epsg).transform, geom)


# ------------------------------------------------------------------ shape validation


def _ring_from_geojson(geojson: Any) -> list[tuple[float, float]]:
    if not isinstance(geojson, dict):
        raise _invalid("The field boundary must be a GeoJSON Polygon.")
    if geojson.get("type") != "Polygon":
        raise _invalid(
            f"The field boundary must be a GeoJSON Polygon, not {geojson.get('type') or 'nothing'}."
        )
    coordinates = geojson.get("coordinates")
    if not isinstance(coordinates, list) or not coordinates:
        raise _invalid("The field boundary has no coordinates.")
    if len(coordinates) > 1:
        raise _invalid("A field boundary must be a single ring; holes are not supported.")
    ring = coordinates[0]
    if not isinstance(ring, list):
        raise _invalid("The field boundary ring must be a list of coordinate pairs.")

    points: list[tuple[float, float]] = []
    for position in ring:
        if not isinstance(position, list | tuple) or len(position) < 2:
            raise _invalid("Every coordinate must be a [longitude, latitude] pair.")
        try:
            lng, lat = float(position[0]), float(position[1])
        except (TypeError, ValueError) as exc:
            raise _invalid("Coordinates must be numbers.") from exc
        if not (math.isfinite(lng) and math.isfinite(lat)):
            raise _invalid("Coordinates must be finite numbers.")
        if not -180.0 <= lng <= 180.0:
            raise _invalid(f"Longitude {lng} is outside the valid range -180 to 180.")
        if not -90.0 <= lat <= 90.0:
            raise _invalid(f"Latitude {lat} is outside the valid range -90 to 90.")
        points.append((lng, lat))

    if len(points) < MIN_VERTICES + 1 or points[0] != points[-1]:
        if len(points) >= MIN_VERTICES and points[0] != points[-1]:
            raise _invalid(
                "The field boundary is not closed: the last coordinate must repeat the first."
            )
        raise _invalid(f"A field boundary needs at least {MIN_VERTICES} corners.")
    return points


def parse_polygon(geojson: Any) -> tuple[Polygon, int]:
    """Validate a GeoJSON Polygon and return ``(polygon, distinct vertex count)``."""
    ring = _ring_from_geojson(geojson)
    distinct = list(dict.fromkeys(ring[:-1]))
    if len(distinct) < MIN_VERTICES:
        raise _invalid(
            f"A field boundary needs at least {MIN_VERTICES} different corners; "
            f"this one has {len(distinct)}."
        )
    if len(distinct) > MAX_VERTICES:
        raise _invalid(
            f"A field boundary may have at most {MAX_VERTICES} corners; this one has "
            f"{len(distinct)}. Simplify the shape and draw it again.",
            code="field_vertex_limit",
        )

    polygon = shape({"type": "Polygon", "coordinates": [ring]})
    if not isinstance(polygon, Polygon):
        raise _invalid("The field boundary must be a single polygon.")
    if polygon.is_empty:
        raise _invalid("The field boundary is empty.")
    if not polygon.is_valid:
        reason = explain_validity(polygon)
        if "Self-intersection" in reason:
            raise _invalid(
                "The boundary crosses itself. Draw it again without crossing lines.",
                code="field_self_intersection",
                reason=reason,
            )
        raise _invalid(f"The field boundary is not a valid shape ({reason}).")
    return polygon, len(distinct)


def check_country(polygon: Polygon, country: str) -> None:
    """Reject a polygon drawn outside the farmer's country."""
    box = COUNTRY_BBOX.get(country)
    if box is None:
        raise _invalid(f"No boundary box is configured for country '{country}'.")
    min_lng, min_lat, max_lng, max_lat = box
    p_min_lng, p_min_lat, p_max_lng, p_max_lat = polygon.bounds
    if p_min_lng < min_lng or p_max_lng > max_lng or p_min_lat < min_lat or p_max_lat > max_lat:
        raise _invalid(
            f"This field is outside {COUNTRY_LABEL.get(country, country)}. "
            "Check the crop programme and draw the field in the right country.",
            code="field_outside_country",
            country=country,
        )


def measure(polygon: Polygon, epsg: int | None = None) -> AreaResult:
    """Area of ``polygon`` in square metres, acres and hectares."""
    if epsg is None:
        centroid = polygon.centroid
        epsg = utm_epsg(centroid.x, centroid.y)
    m2 = float(project(polygon, epsg).area)
    return AreaResult(m2=m2, acre=m2 / M2_PER_ACRE, ha=m2 / M2_PER_HECTARE)


def check_area(area: AreaResult) -> None:
    minimum, maximum = area_limits()
    if area.m2 < minimum:
        raise _invalid(
            f"This field is too small: {area.m2:.0f} m2. The smallest field we record is "
            f"{minimum:.0f} m2.",
            code="field_area_too_small",
            area_m2=round(area.m2, 2),
        )
    if area.m2 > maximum:
        raise _invalid(
            f"This field is too large: {area.ha:.1f} ha. The largest field we record is "
            f"{maximum / M2_PER_HECTARE:.0f} ha. Map it as separate fields.",
            code="field_area_too_large",
            area_m2=round(area.m2, 2),
        )


def resolve_pin(
    polygon: Polygon, epsg: int, pin_lat: float | None, pin_lng: float | None
) -> tuple[float, float]:
    """Validate a pin, or fall back to the representative point of the polygon."""
    if pin_lat is None or pin_lng is None:
        point = polygon.representative_point()
        return float(point.y), float(point.x)
    if not (math.isfinite(pin_lat) and math.isfinite(pin_lng)):
        raise _invalid("The pin coordinates must be finite numbers.", code="field_pin_invalid")
    from shapely.geometry import Point

    pin = Point(pin_lng, pin_lat)
    if not polygon.covers(pin):
        distance = project(pin, epsg).distance(project(polygon, epsg))
        if distance > PIN_MAX_DISTANCE_M:
            raise _invalid(
                f"The pin is {distance:.0f} m from the field. Place it inside the boundary "
                f"or within {PIN_MAX_DISTANCE_M:.0f} m of it.",
                code="field_pin_outside",
                distance_m=round(distance, 1),
            )
    return float(pin_lat), float(pin_lng)


# ------------------------------------------------------------------------- overlaps


def find_overlaps(
    polygon: Polygon,
    candidates: Iterable[CandidateField],
    *,
    exclude_field_id: str | None = None,
) -> list[OverlapConflict]:
    """Return every candidate whose intersection with ``polygon`` has real area.

    The caller prefilters by bounding box; this function is the exact test. Areas are
    measured in the UTM zone of the new polygon so both shapes are compared in metres.
    Fields that merely touch along a boundary intersect in zero area and are skipped.
    """
    items = [c for c in candidates if c.id != exclude_field_id]
    if not items:
        return []

    centroid = polygon.centroid
    epsg = utm_epsg(centroid.x, centroid.y)
    target = project(polygon, epsg)
    target_area = float(target.area) or 1.0

    geometries: list[BaseGeometry] = []
    kept: list[CandidateField] = []
    for candidate in items:
        try:
            geom = shape(candidate.geometry)
        except Exception:  # noqa: BLE001 - a stored shape must never break a save
            continue
        if geom.is_empty or not isinstance(geom, Polygon):
            continue
        geometries.append(project(geom, epsg))
        kept.append(candidate)
    if not geometries:
        return []

    tree = STRtree(geometries)
    conflicts: list[OverlapConflict] = []
    for index in tree.query(target):
        other = geometries[int(index)]
        if not target.intersects(other):
            continue
        overlap = float(target.intersection(other).area)
        if overlap <= OVERLAP_TOLERANCE_M2:
            continue  # touching edges, or floating point noise
        candidate = kept[int(index)]
        conflicts.append(
            OverlapConflict(
                field_id=candidate.id,
                field_code=candidate.field_id,
                farmer_id=candidate.farmer_id,
                farmer_name=candidate.farmer_name,
                sawie_id=candidate.sawie_id,
                overlap_m2=overlap,
                overlap_percent_of_new_field=overlap / target_area * 100.0,
            )
        )
    conflicts.sort(key=lambda c: c.overlap_m2, reverse=True)
    return conflicts


def raise_for_overlaps(conflicts: Sequence[OverlapConflict]) -> None:
    """Turn overlap conflicts into a 409 that names every conflicting field."""
    if not conflicts:
        return
    first = conflicts[0]
    others = f" and {len(conflicts) - 1} other field(s)" if len(conflicts) > 1 else ""
    raise ConflictError(
        f"This boundary overlaps field {first.field_code} ({first.farmer_name}, SAWIE ID "
        f"{first.sawie_id}) by {first.overlap_m2:.0f} m2{others}. Fields may touch but "
        "must not overlap.",
        code="field_overlap",
        details={"conflicts": [c.as_dict() for c in conflicts]},
    )


# ----------------------------------------------------------------------- entry point


def prepare_geometry(
    geojson: Any,
    *,
    country: str,
    pin_lat: float | None = None,
    pin_lng: float | None = None,
) -> GeometryResult:
    """Validate a drawn boundary and derive everything stored with it.

    Raises :class:`ValidationAppError` for any shape, country, area or pin problem.
    Overlap is checked separately, because the caller needs the candidate list.
    """
    polygon, vertex_count = parse_polygon(geojson)
    check_country(polygon, country)

    centroid = polygon.centroid
    epsg = utm_epsg(centroid.x, centroid.y)
    area = measure(polygon, epsg)
    check_area(area)
    resolved_lat, resolved_lng = resolve_pin(polygon, epsg, pin_lat, pin_lng)

    min_lng, min_lat, max_lng, max_lat = polygon.bounds
    ring = [[float(x), float(y)] for x, y in polygon.exterior.coords]
    return GeometryResult(
        geometry={"type": "Polygon", "coordinates": [ring]},
        area=area,
        vertex_count=vertex_count,
        bbox_min_lng=float(min_lng),
        bbox_min_lat=float(min_lat),
        bbox_max_lng=float(max_lng),
        bbox_max_lat=float(max_lat),
        centroid_lat=float(centroid.y),
        centroid_lng=float(centroid.x),
        pin_lat=resolved_lat,
        pin_lng=resolved_lng,
    )
