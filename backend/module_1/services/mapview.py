"""The overview map: every field in the filter as a GeoJSON feature.

The shape is the one Harvest Radar's map already uses, because the frontend reuses the
map components Module 2 exports and the colouring Module 4 defines. The dashboard adds
one thing the radar does not need: the crop, so the map can be coloured by crop
programme as well as by readiness.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from core.deps import CurrentOfficer
from module_1 import config
from module_1.services import sources
from module_1.services.filters import DashboardFilters


def build_map(session: Session, f: DashboardFilters, officer: CurrentOfficer) -> dict[str, Any]:
    """A FeatureCollection of at most ``config.MAP_FEATURE_LIMIT`` fields."""
    rows = sources.readiness_rows(session, f, officer, include_geometry=True)
    features = [
        {
            "type": "Feature",
            "id": row.field_id,
            "geometry": row.geometry,
            "properties": {
                "field_id": row.field_id,
                "field_code": row.field_code,
                "farmer_id": row.farmer_id,
                "farmer_name": row.farmer_name,
                "sawie_id": row.sawie_id,
                "crop": row.crop,
                "status": row.status,
                "status_label": row.status_label,
                "overdue": row.overdue,
                "pickup_state": row.pickup_state,
                "area": row.area_acre if f.area_unit(row.crop) == "acre" else row.area_ha,
                "area_unit": f.area_unit(row.crop),
                "centroid": [row.centroid_lng, row.centroid_lat],
            },
        }
        for row in rows[: config.MAP_FEATURE_LIMIT]
    ]
    return {
        "type": "FeatureCollection",
        "features": features,
        "total": len(rows),
        "returned": len(features),
        "truncated": len(rows) > config.MAP_FEATURE_LIMIT,
        "crop": f.crop,
        "season_year": f.season_year,
        "scope": f.scope,
        "generated_at": datetime.now(UTC),
    }


__all__ = ["build_map"]
