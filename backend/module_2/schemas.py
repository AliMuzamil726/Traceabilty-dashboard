"""Request and response schemas for Module 2 (Register Farmer).

Shape rules that apply throughout: snake_case keys, IDs as strings except the SAWIE ID
(which is a number by design), dates as ``YYYY-MM-DD`` and timestamps as ISO 8601 UTC.

Input schemas here only check types and coarse limits. The real rules - CNIC length,
phone format, which fields a crop requires - live in
:mod:`module_2.services.validators` so that they are enforced identically by the API,
by the public API and by the seed-independent unit tests.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict
from pydantic import Field as PydanticField

from module_2.models import CROP_COTTON, CROP_HEMP

Crop = Literal["cotton", "hemp"]
SHORT = Annotated[str, PydanticField(min_length=1, max_length=120)]


class OrmModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --------------------------------------------------------------------------- inputs


class FarmerIn(BaseModel):
    """One payload for both crop programmes; the crop decides which fields are required.

    Location arrives as codes from the cascade. ``tehsil_name`` carries a typed tehsil
    for districts that have no seeded list, in which case ``tehsil_code`` is null.
    """

    crop: Crop
    id_number: Annotated[str, PydanticField(min_length=1, max_length=64)]
    name: Annotated[str, PydanticField(min_length=1, max_length=120)]
    field_office_id: Annotated[str, PydanticField(min_length=1, max_length=36)]

    # Cotton (Pakistan)
    father_name: str | None = PydanticField(default=None, max_length=120)
    province_code: str | None = PydanticField(default=None, max_length=64)
    district_code: str | None = PydanticField(default=None, max_length=64)
    tehsil_code: str | None = PydanticField(default=None, max_length=64)
    tehsil_name: str | None = PydanticField(default=None, max_length=120)
    village: str | None = PydanticField(default=None, max_length=120)

    # Hemp (United Kingdom)
    farm_name: str | None = PydanticField(default=None, max_length=120)
    home_office_licence_no: str | None = PydanticField(default=None, max_length=40)
    postcode: str | None = PydanticField(default=None, max_length=12)
    #: Only honoured when the postcode could not be resolved by any source.
    county: str | None = PydanticField(default=None, max_length=120)
    region: str | None = PydanticField(default=None, max_length=120)

    phone: str | None = PydanticField(default=None, max_length=32)

    # This season's crop data (upserted into farmer_season_profiles)
    variety: SHORT
    tenure: SHORT
    previous_crop: str | None = PydanticField(default=None, max_length=120)
    season_year: int | None = PydanticField(default=None, ge=2000, le=2100)
    notes: str | None = PydanticField(default=None, max_length=2000)


class GeometryIn(BaseModel):
    """A drawn boundary. Validated and re-measured by the geometry engine."""

    geometry: dict[str, Any]
    pin_lat: float | None = PydanticField(default=None, ge=-90, le=90)
    pin_lng: float | None = PydanticField(default=None, ge=-180, le=180)


class FieldUpdateIn(BaseModel):
    geometry: dict[str, Any] | None = None
    pin_lat: float | None = PydanticField(default=None, ge=-90, le=90)
    pin_lng: float | None = PydanticField(default=None, ge=-180, le=180)


class ValidateGeometryIn(GeometryIn):
    """Live validation while drawing. ``exclude_field_id`` is the field being edited."""

    farmer_id: Annotated[str, PydanticField(min_length=1, max_length=36)]
    exclude_field_id: str | None = PydanticField(default=None, max_length=36)


# -------------------------------------------------------------------------- outputs


class OfficerRefOut(BaseModel):
    id: str | None
    code: str | None
    full_name: str | None


class FieldOfficeRefOut(BaseModel):
    id: str
    code: str
    name: str


class SeasonProfileOut(OrmModel):
    season_year: int
    variety: str
    tenure: str
    previous_crop: str | None
    notes: str | None
    updated_at: datetime


class FarmerListItemOut(BaseModel):
    """List row. The ID number and phone are masked for every caller."""

    id: str
    sawie_id: int
    crop: Crop
    country: str
    name: str
    father_name: str | None
    farm_name: str | None
    id_number_masked: str
    phone_masked: str | None
    location_summary: str
    field_office: FieldOfficeRefOut | None
    registered_by: OfficerRefOut | None
    field_count: int
    has_fields: bool
    created_at: datetime


class FarmerOut(BaseModel):
    """One farmer. ``id_number`` and ``phone`` hold masked values unless the caller
    is the registering officer or an administrator."""

    id: str
    sawie_id: int
    crop: Crop
    country: str
    name: str
    father_name: str | None
    farm_name: str | None
    id_number: str
    phone: str | None
    sensitive_visible: bool

    province: str | None
    district: str | None
    tehsil: str | None
    village: str | None
    home_office_licence_no: str | None
    postcode: str | None
    county: str | None
    region: str | None

    field_office: FieldOfficeRefOut | None
    registered_by: OfficerRefOut | None
    created_at: datetime
    updated_at: datetime


class FarmerPersonalOut(BaseModel):
    """The personal data a lookup returns so the form can pre-fill it.

    Crop data is deliberately absent: the officer enters this season's values.
    """

    name: str
    father_name: str | None
    farm_name: str | None
    phone: str | None
    province_code: str | None
    province: str | None
    district_code: str | None
    district: str | None
    tehsil_code: str | None
    tehsil: str | None
    village: str | None
    home_office_licence_no: str | None
    postcode: str | None
    county: str | None
    region: str | None
    field_office_id: str | None


class FarmerLookupOut(BaseModel):
    """Answer to "is this ID number already registered?".

    * not registered: ``exists`` false and a ``next_sawie_id_preview`` to show as a
      preview only, because the real ID is allocated when the farmer is saved;
    * registered: the SAWIE ID and the personal data, plus who registered it and when;
    * registered under the other crop: ``crop_mismatch`` true, and the caller must stop.
    """

    exists: bool
    crop: Crop
    id_number_masked: str | None = None
    next_sawie_id_preview: int | None = None
    sawie_id: int | None = None
    farmer_id: str | None = None
    crop_mismatch: bool = False
    registered_crop: Crop | None = None
    registered_country: str | None = None
    registered_by: OfficerRefOut | None = None
    registered_at: datetime | None = None
    field_office: FieldOfficeRefOut | None = None
    #: True when another officer registered this farmer, so the UI can say so.
    registered_by_other_officer: bool = False
    personal: FarmerPersonalOut | None = None
    field_count: int = 0


class FieldOut(BaseModel):
    id: str
    field_id: str
    farmer_id: str
    geometry: dict[str, Any]
    area_m2: float
    area_acre: float
    area_ha: float
    vertex_count: int
    centroid_lat: float
    centroid_lng: float
    pin_lat: float
    pin_lng: float
    bbox: list[float]
    created_at: datetime
    updated_at: datetime


class FarmerFieldsOut(BaseModel):
    items: list[FieldOut]
    total: int
    next_field_id_preview: str


class FarmerCompletenessOut(BaseModel):
    """A farmer is only usable downstream once at least one field is mapped."""

    has_fields: bool
    field_count: int
    total_area_acre: float
    total_area_ha: float
    ready_for_fieldbook: bool
    missing: list[str]


class FarmerProfileOut(BaseModel):
    farmer: FarmerOut
    season_profiles: list[SeasonProfileOut]
    fields: list[FieldOut]
    completeness: FarmerCompletenessOut


class FarmerSavedOut(BaseModel):
    """Result of a registration or an update, with the final SAWIE ID."""

    farmer: FarmerOut
    created: bool
    season_profile: SeasonProfileOut
    next_field_id_preview: str


class OverlapConflictOut(BaseModel):
    field_id: str
    field_code: str
    farmer_id: str
    farmer_name: str
    sawie_id: int
    overlap_m2: float
    overlap_percent_of_new_field: float


class GeometryValidationOut(BaseModel):
    """Live feedback while drawing: measurements plus every conflict found."""

    valid: bool
    area_m2: float | None = None
    area_acre: float | None = None
    area_ha: float | None = None
    vertex_count: int | None = None
    centroid_lat: float | None = None
    centroid_lng: float | None = None
    pin_lat: float | None = None
    pin_lng: float | None = None
    error_code: str | None = None
    message: str | None = None
    conflicts: list[OverlapConflictOut] = []


class MapFeatureOut(BaseModel):
    """One field on the map layer. Geometry is omitted in clustered (low zoom) mode."""

    id: str
    field_id: str
    farmer_id: str
    farmer_name: str
    sawie_id: int
    crop: Crop
    area_acre: float
    area_ha: float
    pin_lat: float
    pin_lng: float
    geometry: dict[str, Any] | None = None


class MapFieldsOut(BaseModel):
    items: list[MapFeatureOut]
    total: int
    returned: int
    truncated: bool
    #: ``outlines`` above the geometry zoom threshold, ``points`` below it.
    mode: Literal["outlines", "points"]
    limit: int


class LocationOptionOut(BaseModel):
    value: str
    label: str
    level: str
    parent_code: str | None = None


class LocationListOut(BaseModel):
    items: list[LocationOptionOut]
    #: True when the form should offer "Other (type manually)".
    allow_manual: bool = False


class VillageSuggestionsOut(BaseModel):
    items: list[str]


class PostcodeOut(BaseModel):
    postcode: str
    county: str | None
    region: str | None
    source: str
    resolved: bool
    #: Only true when nothing could resolve the postcode, which is the single case
    #: where the officer may type the county and region.
    editable: bool


CROP_LABELS: dict[str, str] = {CROP_COTTON: "Cotton", CROP_HEMP: "Hemp"}

__all__ = [
    "CROP_LABELS",
    "FarmerCompletenessOut",
    "FarmerFieldsOut",
    "FarmerIn",
    "FarmerListItemOut",
    "FarmerLookupOut",
    "FarmerOut",
    "FarmerPersonalOut",
    "FarmerProfileOut",
    "FarmerSavedOut",
    "FieldOfficeRefOut",
    "FieldOut",
    "FieldUpdateIn",
    "GeometryIn",
    "GeometryValidationOut",
    "LocationListOut",
    "LocationOptionOut",
    "MapFeatureOut",
    "MapFieldsOut",
    "OfficerRefOut",
    "OverlapConflictOut",
    "PostcodeOut",
    "SeasonProfileOut",
    "ValidateGeometryIn",
    "VillageSuggestionsOut",
]
