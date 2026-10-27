"""Creating, editing and deleting mapped fields.

Two things in here matter more than the rest.

**The overlap check runs twice.** Once while the officer draws, through
``POST /fields/validate-geometry``, so the map can show the conflict live; and again
immediately before the INSERT, inside the saving transaction. The second check is not
redundant: between the last keystroke and the save, another officer may have saved an
overlapping boundary. On SQLite every transaction opens with ``BEGIN IMMEDIATE``
(DECISIONS D-006), so two concurrent saves serialise and the second one reads the
first one's committed field and is rejected.

**Deleting and reshaping ask permission first.** Module 2 owns fields but cannot know
whether a fieldbook or a delivery already depends on one, so it calls the guards
``field.can_delete`` and ``field.can_edit_geometry`` and lets Modules 3 and 5 refuse.
While those modules are unbuilt no checks are registered and both actions are allowed.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from core import audit, events
from core.errors import NotFoundError, ValidationAppError
from core.events import EventBus
from core.guards import FIELD_CAN_DELETE, FIELD_CAN_EDIT_GEOMETRY, GuardRegistry
from core.guards import guards as default_guards
from module_2.models import Farmer, Field
from module_2.repository import FarmerRepository, FieldRepository
from module_2.schemas import (
    FieldOut,
    GeometryValidationOut,
    MapFeatureOut,
    MapFieldsOut,
    OverlapConflictOut,
)
from module_2.services import geometry as geo
from module_2.services import ids

#: Below this zoom the map layer returns centroids for clustering instead of outlines.
GEOMETRY_ZOOM = 13

#: Hard cap on features per map request, as specified.
MAP_FEATURE_LIMIT = 2000


class FieldService:
    def __init__(
        self,
        session: Session,
        *,
        bus: EventBus | None = None,
        guards: GuardRegistry | None = None,
    ) -> None:
        self.session = session
        self.bus = bus or events.bus
        self.guards = guards or default_guards
        self.fields = FieldRepository(session)
        self.farmers = FarmerRepository(session)

    # ----------------------------------------------------------------- lookups

    def require_farmer(self, farmer_id: str) -> Farmer:
        farmer = self.farmers.get(farmer_id)
        if farmer is None:
            raise NotFoundError(
                "That farmer does not exist.",
                code="farmer_not_found",
                details={"farmer_id": farmer_id},
            )
        return farmer

    def require_field(self, field_uuid: str) -> Field:
        field = self.fields.get_active(field_uuid)
        if field is None:
            raise NotFoundError(
                "That field does not exist.",
                code="field_not_found",
                details={"field_id": field_uuid},
            )
        return field

    def list_for_farmer(self, farmer_id: str) -> list[Field]:
        return self.fields.list_for_farmer(farmer_id)

    def next_field_id_preview(self, sawie_id: int) -> str:
        return ids.preview_field_id(self.session, sawie_id)

    # -------------------------------------------------------------- overlap test

    def _candidates(
        self, bbox: tuple[float, float, float, float], exclude_id: str | None
    ) -> list[geo.CandidateField]:
        return [
            geo.CandidateField(
                id=field.id,
                field_id=field.field_id,
                farmer_id=farmer.id,
                farmer_name=farmer.name,
                sawie_id=farmer.sawie_id,
                geometry=field.geometry,
            )
            for field, farmer in self.fields.bbox_candidates(bbox, exclude_id=exclude_id)
        ]

    def _prepare(
        self,
        geojson: Any,
        farmer: Farmer,
        *,
        pin_lat: float | None,
        pin_lng: float | None,
        exclude_field_id: str | None = None,
    ) -> tuple[geo.GeometryResult, list[geo.OverlapConflict]]:
        prepared = geo.prepare_geometry(
            geojson, country=farmer.country, pin_lat=pin_lat, pin_lng=pin_lng
        )
        conflicts = geo.find_overlaps(
            geo.shape(prepared.geometry),  # type: ignore[arg-type]
            self._candidates(prepared.bbox, exclude_field_id),
            exclude_field_id=exclude_field_id,
        )
        return prepared, conflicts

    def validate_geometry(
        self,
        geojson: Any,
        farmer_id: str,
        *,
        pin_lat: float | None = None,
        pin_lng: float | None = None,
        exclude_field_id: str | None = None,
    ) -> GeometryValidationOut:
        """Live feedback while drawing.

        Always answers 200: a half-drawn or overlapping boundary is an expected state
        of the map, not a failed request. ``valid`` says whether Save may be enabled.
        """
        farmer = self.require_farmer(farmer_id)
        try:
            prepared, conflicts = self._prepare(
                geojson,
                farmer,
                pin_lat=pin_lat,
                pin_lng=pin_lng,
                exclude_field_id=exclude_field_id,
            )
        except ValidationAppError as exc:
            return GeometryValidationOut(valid=False, error_code=exc.code, message=exc.message)

        return GeometryValidationOut(
            valid=not conflicts,
            area_m2=round(prepared.area.m2, 2),
            area_acre=round(prepared.area.acre, 4),
            area_ha=round(prepared.area.ha, 4),
            vertex_count=prepared.vertex_count,
            centroid_lat=prepared.centroid_lat,
            centroid_lng=prepared.centroid_lng,
            pin_lat=prepared.pin_lat,
            pin_lng=prepared.pin_lng,
            error_code="field_overlap" if conflicts else None,
            message=(
                f"This boundary overlaps {len(conflicts)} existing field(s)." if conflicts else None
            ),
            conflicts=[OverlapConflictOut(**c.as_dict()) for c in conflicts],
        )

    # ------------------------------------------------------------------- writing

    def create(
        self,
        farmer_id: str,
        geojson: Any,
        *,
        pin_lat: float | None,
        pin_lng: float | None,
        officer_id: str | None,
    ) -> Field:
        farmer = self.require_farmer(farmer_id)
        # Re-validated and re-checked here, inside the saving transaction.
        prepared, conflicts = self._prepare(geojson, farmer, pin_lat=pin_lat, pin_lng=pin_lng)
        geo.raise_for_overlaps(conflicts)

        field = Field(
            field_id=ids.allocate_field_id(self.session, farmer.sawie_id),
            farmer_id=farmer.id,
            geometry=prepared.geometry,
            bbox_min_lat=prepared.bbox_min_lat,
            bbox_min_lng=prepared.bbox_min_lng,
            bbox_max_lat=prepared.bbox_max_lat,
            bbox_max_lng=prepared.bbox_max_lng,
            pin_lat=prepared.pin_lat,
            pin_lng=prepared.pin_lng,
            vertex_count=prepared.vertex_count,
            area_m2=prepared.area.m2,
            area_acre=prepared.area.acre,
            area_ha=prepared.area.ha,
            created_by=officer_id,
            updated_by=officer_id,
        )
        self.fields.add(field)
        audit.record(
            "field",
            field.id,
            audit.ACTION_CREATE,
            officer_id,
            {
                "field_id": {"from": None, "to": field.field_id},
                "area_m2": {"from": None, "to": round(field.area_m2, 2)},
                "vertex_count": {"from": None, "to": field.vertex_count},
            },
            session=self.session,
        )
        self.bus.publish(
            events.FIELD_CREATED,
            {
                "field_id": field.id,
                "field_code": field.field_id,
                "farmer_id": farmer.id,
                "area_m2": round(field.area_m2, 2),
                "bbox": list(prepared.bbox),
            },
            officer_id=officer_id,
            session=self.session,
        )
        self.session.commit()
        return field

    def update(
        self,
        field_uuid: str,
        *,
        geojson: Any | None,
        pin_lat: float | None,
        pin_lng: float | None,
        officer_id: str | None,
    ) -> Field:
        field = self.require_field(field_uuid)
        farmer = self.require_farmer(field.farmer_id)
        geometry_changed = geojson is not None

        if geometry_changed:
            # Downstream modules may refuse a reshape once work depends on this field.
            self.guards.enforce(FIELD_CAN_EDIT_GEOMETRY, field_id=field.id, session=self.session)

        before = {
            "geometry": field.geometry,
            "area_m2": field.area_m2,
            "vertex_count": field.vertex_count,
            "pin_lat": field.pin_lat,
            "pin_lng": field.pin_lng,
        }

        source = geojson if geometry_changed else field.geometry
        prepared, conflicts = self._prepare(
            source,
            farmer,
            pin_lat=pin_lat,
            pin_lng=pin_lng,
            exclude_field_id=field.id,  # a field never conflicts with itself
        )
        geo.raise_for_overlaps(conflicts)

        if geometry_changed:
            field.geometry = prepared.geometry
            field.bbox_min_lat = prepared.bbox_min_lat
            field.bbox_min_lng = prepared.bbox_min_lng
            field.bbox_max_lat = prepared.bbox_max_lat
            field.bbox_max_lng = prepared.bbox_max_lng
            field.vertex_count = prepared.vertex_count
            field.area_m2 = prepared.area.m2
            field.area_acre = prepared.area.acre
            field.area_ha = prepared.area.ha
        field.pin_lat = prepared.pin_lat
        field.pin_lng = prepared.pin_lng
        field.updated_by = officer_id
        self.session.flush()

        diff = audit.compute_diff(
            before,
            {
                "geometry": field.geometry,
                "area_m2": field.area_m2,
                "vertex_count": field.vertex_count,
                "pin_lat": field.pin_lat,
                "pin_lng": field.pin_lng,
            },
        )
        if diff:
            audit.record(
                "field", field.id, audit.ACTION_UPDATE, officer_id, diff, session=self.session
            )
            self.bus.publish(
                events.FIELD_UPDATED,
                {
                    "field_id": field.id,
                    "field_code": field.field_id,
                    "farmer_id": field.farmer_id,
                    "changed": sorted(diff.keys()),
                    "geometry_changed": geometry_changed,
                },
                officer_id=officer_id,
                session=self.session,
            )
        self.session.commit()
        return field

    def delete(self, field_uuid: str, *, officer_id: str | None) -> Field:
        """Soft delete. The field ID is never reissued, so the trail stays readable."""
        field = self.require_field(field_uuid)
        self.guards.enforce(FIELD_CAN_DELETE, field_id=field.id, session=self.session)

        self.fields.soft_delete(field, officer_id)
        audit.record(
            "field",
            field.id,
            audit.ACTION_DELETE,
            officer_id,
            {"deleted_at": {"from": None, "to": field.deleted_at}},
            session=self.session,
        )
        self.bus.publish(
            events.FIELD_DELETED,
            {
                "field_id": field.id,
                "field_code": field.field_id,
                "farmer_id": field.farmer_id,
            },
            officer_id=officer_id,
            session=self.session,
        )
        self.session.commit()
        return field

    # ----------------------------------------------------------------- map layer

    def map_fields(
        self,
        bbox: tuple[float, float, float, float] | None,
        *,
        zoom: int | None = None,
        crop: str | None = None,
        limit: int = MAP_FEATURE_LIMIT,
    ) -> MapFieldsOut:
        """Every field in the database, for the context layer under the drawing.

        Outlines are only worth sending when they are more than a few pixels across,
        so below :data:`GEOMETRY_ZOOM` the response carries centroids for clustering.
        """
        capped = max(1, min(limit, MAP_FEATURE_LIMIT))
        with_geometry = zoom is None or zoom >= GEOMETRY_ZOOM
        total = self.fields.count_map_fields(bbox, crop=crop)
        rows = self.fields.map_fields(bbox, crop=crop, limit=capped)
        return MapFieldsOut(
            items=[
                MapFeatureOut(
                    id=field.id,
                    field_id=field.field_id,
                    farmer_id=farmer.id,
                    farmer_name=farmer.name,
                    sawie_id=farmer.sawie_id,
                    crop=farmer.crop,  # type: ignore[arg-type]
                    area_acre=round(field.area_acre, 4),
                    area_ha=round(field.area_ha, 4),
                    pin_lat=field.pin_lat,
                    pin_lng=field.pin_lng,
                    geometry=field.geometry if with_geometry else None,
                )
                for field, farmer in rows
            ],
            total=total,
            returned=len(rows),
            truncated=total > len(rows),
            mode="outlines" if with_geometry else "points",
            limit=capped,
        )

    # -------------------------------------------------------------- presentation

    @staticmethod
    def to_out(field: Field) -> FieldOut:
        polygon = geo.shape(field.geometry)
        centroid = polygon.centroid
        return FieldOut(
            id=field.id,
            field_id=field.field_id,
            farmer_id=field.farmer_id,
            geometry=field.geometry,
            area_m2=round(field.area_m2, 2),
            area_acre=round(field.area_acre, 4),
            area_ha=round(field.area_ha, 4),
            vertex_count=field.vertex_count,
            centroid_lat=float(centroid.y),
            centroid_lng=float(centroid.x),
            pin_lat=field.pin_lat,
            pin_lng=field.pin_lng,
            bbox=[
                field.bbox_min_lng,
                field.bbox_min_lat,
                field.bbox_max_lng,
                field.bbox_max_lat,
            ],
            created_at=field.created_at,
            updated_at=field.updated_at,
        )


__all__ = ["GEOMETRY_ZOOM", "MAP_FEATURE_LIMIT", "FieldService"]
