"""Registration and updating of farmers, and the existing-farmer lookup.

The rule that shapes this file: **one person, one SAWIE ID, for life.** The normalised
ID number is the identity, so registering a farmer who already exists is an update of
their personal data plus a new season profile, never a second farmer. That is why
:meth:`FarmerService.save` has one entry point for both cases and why the SAWIE ID is
allocated inside the saving transaction rather than when the form is opened.

Personal data (permanent) and crop data (per season) are deliberately split: the
lookup returns only the personal half, so the officer always enters this season's
variety, tenure and previous crop rather than inheriting last season's by accident.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from core import audit, events
from core.config import Settings
from core.deps import CurrentOfficer
from core.errors import ConflictError, NotFoundError, ValidationAppError
from core.events import EventBus
from core.pagination import Page, PageParams
from module_2.models import (
    COUNTRY_GB,
    CROP_COTTON,
    CROP_COUNTRY,
    Farmer,
    FarmerSeasonProfile,
)
from module_2.repository import FarmerRepository, FieldRepository, SeasonProfileRepository
from module_2.schemas import (
    CROP_LABELS,
    FarmerCompletenessOut,
    FarmerIn,
    FarmerListItemOut,
    FarmerLookupOut,
    FarmerOut,
    FarmerPersonalOut,
    FarmerProfileOut,
    FarmerSavedOut,
    FieldOfficeRefOut,
    OfficerRefOut,
    SeasonProfileOut,
)
from module_2.services import ids
from module_2.services.fields import FieldService
from module_2.services.locations import LocationService
from module_2.services.permissions import require_may_act
from module_2.services.postcode import PostcodeService
from module_2.services.validators import (
    mask_id_number,
    mask_phone,
    normalise_farm_name,
    normalise_id_number,
    normalise_licence_no,
    normalise_person_name,
    normalise_phone,
    normalise_postcode,
    normalise_village,
    sanitise_text,
    validate_crop,
)
from shared.models.officer import SEES_ALL_ROLES
from shared.repositories.master_lists import MasterListRepository
from shared.repositories.officers import OfficerRepository
from shared.repositories.offices import FieldOfficeRepository

#: Personal columns an update may change. The SAWIE ID, crop, country, ID number and
#: registering officer are deliberately absent: those are identity, not detail.
EDITABLE_PERSONAL_FIELDS = (
    "name",
    "father_name",
    "farm_name",
    "phone_norm",
    "phone_display",
    "province",
    "district",
    "tehsil",
    "village",
    "location_id",
    "home_office_licence_no",
    "postcode_norm",
    "county",
    "region",
    "field_office_id",
)

MASTER_VARIETY = "variety"
MASTER_TENURE = "tenure"
MASTER_PREVIOUS_CROP = "previous_crop"


def current_season_year() -> int:
    return datetime.now(UTC).year


@dataclass(frozen=True)
class _Resolved:
    """A validated payload, ready to write to the two tables."""

    crop: str
    country: str
    id_number_norm: str
    id_number_display: str
    personal: dict[str, Any]
    season: dict[str, Any]
    season_year: int


class FarmerService:
    def __init__(
        self,
        session: Session,
        *,
        settings: Settings | None = None,
        bus: EventBus | None = None,
    ) -> None:
        self.session = session
        self.settings = settings
        self.bus = bus or events.bus
        self.farmers = FarmerRepository(session)
        self.profiles = SeasonProfileRepository(session)
        self.fields = FieldRepository(session)
        self.offices = FieldOfficeRepository(session)
        self.officers = OfficerRepository(session)
        self.master = MasterListRepository(session)
        self.locations = LocationService(session)

    # ------------------------------------------------------------------ permissions

    def may_see_sensitive(self, farmer: Farmer, officer: CurrentOfficer | None) -> bool:
        """Full ID numbers and phones: the registering officer or an administrator."""
        if officer is None:
            return False
        return officer.role in SEES_ALL_ROLES or farmer.registered_by == officer.id

    @staticmethod
    def scope_for(officer: CurrentOfficer | None) -> str | None:
        """Officers see the farmers they registered; administrators see all."""
        if officer is None or officer.role in SEES_ALL_ROLES:
            return None
        return officer.id

    # --------------------------------------------------------------------- lookup

    def lookup(self, raw_id_number: str, crop_value: str) -> FarmerLookupOut:
        crop = validate_crop(crop_value)
        id_number_norm, id_number_display = normalise_id_number(raw_id_number, crop)
        existing = self.farmers.get_by_id_number(id_number_norm)

        if existing is None:
            return FarmerLookupOut(
                exists=False,
                crop=crop,  # type: ignore[arg-type]
                id_number_masked=mask_id_number(id_number_display),
                next_sawie_id_preview=ids.preview_sawie_id(self.session),
            )

        office = self.offices.get(existing.field_office_id)
        registrar = self.officers.get(existing.registered_by) if existing.registered_by else None
        mismatch = existing.crop != crop
        return FarmerLookupOut(
            exists=True,
            crop=crop,  # type: ignore[arg-type]
            id_number_masked=mask_id_number(existing.id_number_display),
            sawie_id=existing.sawie_id,
            farmer_id=existing.id,
            crop_mismatch=mismatch,
            registered_crop=existing.crop,  # type: ignore[arg-type]
            registered_country=existing.country,
            registered_by=self._officer_ref(registrar),
            registered_at=existing.created_at,
            field_office=self._office_ref(office),
            registered_by_other_officer=False,
            personal=None if mismatch else self._personal(existing),
            field_count=self.fields.count_for_farmer(existing.id),
        )

    def lookup_for_officer(
        self, raw_id_number: str, crop_value: str, officer: CurrentOfficer
    ) -> FarmerLookupOut:
        """Lookup, with the "registered by someone else" notice resolved for this officer."""
        result = self.lookup(raw_id_number, crop_value)
        if not result.exists:
            return result

        # The notice is about who did the registering, not which office the farmer was
        # filed under: an officer may legitimately register a farmer to another office
        # in their country, and must not then be warned about their own work.
        registrar_id = result.registered_by.id if result.registered_by else None
        if registrar_id is not None:
            by_someone_else = registrar_id != officer.id
        else:
            # No registering officer recorded: fall back to comparing offices.
            by_someone_else = (
                result.field_office is not None
                and officer.field_office_id is not None
                and result.field_office.id != officer.field_office_id
            )
        return result.model_copy(update={"registered_by_other_officer": by_someone_else})

    # ----------------------------------------------------------------------- saving

    def save(self, payload: FarmerIn, officer: CurrentOfficer) -> FarmerSavedOut:
        """Register a new farmer, or update an existing one and add this season's profile."""
        resolved = self._resolve(payload, officer)
        existing = self.farmers.get_by_id_number(resolved.id_number_norm)

        if existing is None:
            farmer, created = self._create(resolved, officer), True
        else:
            self._guard_crop(existing, resolved.crop)
            farmer, created = self._update(existing, resolved, officer), False

        profile = self._upsert_season_profile(farmer, resolved, officer)
        self.session.commit()

        return FarmerSavedOut(
            farmer=self.to_out(farmer, officer),
            created=created,
            season_profile=SeasonProfileOut.model_validate(profile),
            next_field_id_preview=ids.preview_field_id(self.session, farmer.sawie_id),
        )

    def update(self, farmer_id: str, payload: FarmerIn, officer: CurrentOfficer) -> FarmerSavedOut:
        """Update one farmer by id. The ID number may not be changed to another person's."""
        farmer = self.require_farmer(farmer_id)
        require_may_act(farmer, officer)
        resolved = self._resolve(payload, officer)
        self._guard_crop(farmer, resolved.crop)
        if resolved.id_number_norm != farmer.id_number_norm:
            clash = self.farmers.get_by_id_number(resolved.id_number_norm)
            if clash is not None and clash.id != farmer.id:
                raise ConflictError(
                    f"That ID number already belongs to SAWIE ID {clash.sawie_id}.",
                    code="farmer_duplicate_id_number",
                    details={"sawie_id": clash.sawie_id, "farmer_id": clash.id},
                )
            farmer.id_number_norm = resolved.id_number_norm
            farmer.id_number_display = resolved.id_number_display

        self._update(farmer, resolved, officer)
        profile = self._upsert_season_profile(farmer, resolved, officer)
        self.session.commit()
        return FarmerSavedOut(
            farmer=self.to_out(farmer, officer),
            created=False,
            season_profile=SeasonProfileOut.model_validate(profile),
            next_field_id_preview=ids.preview_field_id(self.session, farmer.sawie_id),
        )

    def _create(self, resolved: _Resolved, officer: CurrentOfficer) -> Farmer:
        sawie_id = ids.allocate_sawie_id(self.session)
        farmer = Farmer(
            sawie_id=sawie_id,
            crop=resolved.crop,
            country=resolved.country,
            id_number_norm=resolved.id_number_norm,
            id_number_display=resolved.id_number_display,
            registered_by=officer.id,
            created_by=officer.id,
            updated_by=officer.id,
            **resolved.personal,
        )
        self.farmers.add(farmer)
        audit.record(
            "farmer",
            farmer.id,
            audit.ACTION_CREATE,
            officer.id,
            {"sawie_id": {"from": None, "to": sawie_id}, "crop": {"from": None, "to": farmer.crop}},
            session=self.session,
        )
        self.bus.publish(
            events.FARMER_REGISTERED,
            {
                "farmer_id": farmer.id,
                "sawie_id": farmer.sawie_id,
                "crop": farmer.crop,
                "country": farmer.country,
                "field_office_id": farmer.field_office_id,
            },
            officer_id=officer.id,
            session=self.session,
        )
        return farmer

    def _update(self, farmer: Farmer, resolved: _Resolved, officer: CurrentOfficer) -> Farmer:
        before = {key: getattr(farmer, key) for key in EDITABLE_PERSONAL_FIELDS}
        for key, value in resolved.personal.items():
            setattr(farmer, key, value)
        farmer.updated_by = officer.id
        after = {key: getattr(farmer, key) for key in EDITABLE_PERSONAL_FIELDS}
        diff = audit.compute_diff(before, after)
        self.session.flush()

        if diff:
            audit.record(
                "farmer", farmer.id, audit.ACTION_UPDATE, officer.id, diff, session=self.session
            )
            self.bus.publish(
                events.FARMER_UPDATED,
                {
                    "farmer_id": farmer.id,
                    "sawie_id": farmer.sawie_id,
                    "changed": sorted(diff.keys()),
                },
                officer_id=officer.id,
                session=self.session,
            )
        return farmer

    def _upsert_season_profile(
        self, farmer: Farmer, resolved: _Resolved, officer: CurrentOfficer
    ) -> FarmerSeasonProfile:
        profile = self.profiles.get_for_season(farmer.id, resolved.season_year)
        if profile is None:
            profile = FarmerSeasonProfile(
                farmer_id=farmer.id,
                season_year=resolved.season_year,
                created_by=officer.id,
                updated_by=officer.id,
                **resolved.season,
            )
            self.profiles.add(profile)
            audit.record(
                "farmer_season_profile",
                profile.id,
                audit.ACTION_CREATE,
                officer.id,
                {"season_year": {"from": None, "to": resolved.season_year}},
                session=self.session,
            )
            return profile

        before = {key: getattr(profile, key) for key in resolved.season}
        for key, value in resolved.season.items():
            setattr(profile, key, value)
        profile.updated_by = officer.id
        self.session.flush()
        diff = audit.compute_diff(before, {k: getattr(profile, k) for k in resolved.season})
        if diff:
            audit.record(
                "farmer_season_profile",
                profile.id,
                audit.ACTION_UPDATE,
                officer.id,
                diff,
                session=self.session,
            )
        return profile

    # ------------------------------------------------------------------- validation

    def _guard_crop(self, farmer: Farmer, crop: str) -> None:
        """One farmer belongs to one programme: cotton or hemp, never both."""
        if farmer.crop == crop:
            return
        raise ConflictError(
            f"SAWIE ID {farmer.sawie_id} is already registered in the "
            f"{CROP_LABELS[farmer.crop]} programme. One farmer belongs to one programme.",
            code="farmer_crop_mismatch",
            details={
                "sawie_id": farmer.sawie_id,
                "farmer_id": farmer.id,
                "registered_crop": farmer.crop,
                "registered_country": farmer.country,
                "requested_crop": crop,
            },
        )

    def _master_value(
        self, list_key: str, value: str | None, country: str, crop: str
    ) -> str | None:
        """Check a dropdown value against the master list that fed the dropdown."""
        cleaned = sanitise_text(value)
        if cleaned is None:
            return None
        allowed = {
            option.value for option in self.master.options(list_key, country=country, crop=crop)
        }
        if cleaned not in allowed:
            raise ValidationAppError(
                f"'{cleaned}' is not an option in the {list_key.replace('_', ' ')} list.",
                code="master_value_invalid",
                details={
                    "fields": [
                        {
                            "field": list_key,
                            "location": "body",
                            "message": f"Choose a {list_key.replace('_', ' ')} from the list.",
                        }
                    ]
                },
            )
        return cleaned

    def _require_office(self, field_office_id: str, country: str) -> str:
        office = self.offices.get(field_office_id)
        if office is None or not office.active:
            raise ValidationAppError(
                "Choose a field office from the list.",
                code="field_office_invalid",
                details={
                    "fields": [
                        {
                            "field": "field_office_id",
                            "location": "body",
                            "message": "This field office does not exist.",
                        }
                    ]
                },
            )
        if office.country != country:
            raise ValidationAppError(
                f"{office.name} is not in {country}. Choose an office in the farmer's country.",
                code="field_office_country_mismatch",
                details={
                    "fields": [
                        {
                            "field": "field_office_id",
                            "location": "body",
                            "message": "This office belongs to the other crop programme.",
                        }
                    ]
                },
            )
        return office.id

    def _resolve(self, payload: FarmerIn, officer: CurrentOfficer) -> _Resolved:
        crop = validate_crop(payload.crop)
        country = CROP_COUNTRY[crop]
        id_number_norm, id_number_display = normalise_id_number(payload.id_number, crop)
        phone_norm, phone_display = normalise_phone(payload.phone, country)

        personal: dict[str, Any] = {
            "name": normalise_person_name(payload.name, field="name", label="Name"),
            "phone_norm": phone_norm,
            "phone_display": phone_display,
            "field_office_id": self._require_office(payload.field_office_id, country),
            "father_name": None,
            "farm_name": None,
            "province": None,
            "district": None,
            "tehsil": None,
            "village": None,
            "location_id": None,
            "home_office_licence_no": None,
            "postcode_norm": None,
            "county": None,
            "region": None,
        }

        if crop == CROP_COTTON:
            personal.update(self._resolve_cotton(payload, country))
        else:
            personal.update(self._resolve_hemp(payload, id_number_norm))

        season = {
            "variety": self._master_value(MASTER_VARIETY, payload.variety, country, crop),
            "tenure": self._master_value(MASTER_TENURE, payload.tenure, country, crop),
            "previous_crop": self._master_value(
                MASTER_PREVIOUS_CROP, payload.previous_crop, country, crop
            ),
            "notes": sanitise_text(payload.notes, max_length=2000),
        }
        for key in ("variety", "tenure"):
            if not season[key]:
                raise ValidationAppError(
                    f"{key.capitalize()} is required.",
                    code="validation_error",
                    details={
                        "fields": [
                            {
                                "field": key,
                                "location": "body",
                                "message": f"Choose a {key} from the list.",
                            }
                        ]
                    },
                )

        return _Resolved(
            crop=crop,
            country=country,
            id_number_norm=id_number_norm,
            id_number_display=id_number_display,
            personal=personal,
            season=season,
            season_year=payload.season_year or current_season_year(),
        )

    def _resolve_cotton(self, payload: FarmerIn, country: str) -> dict[str, Any]:
        province = self._location_name(payload.province_code, "province", "Province")
        district = self._location_name(payload.district_code, "district", "District")

        tehsil_code = sanitise_text(payload.tehsil_code)
        if tehsil_code:
            tehsil = self._location_name(tehsil_code, "tehsil", "Tehsil or city")
        else:
            tehsil = sanitise_text(payload.tehsil_name)
            if not tehsil:
                raise self._required("tehsil", "Choose a tehsil or city, or type one.")

        most_specific = tehsil_code or payload.district_code or payload.province_code
        return {
            "father_name": normalise_person_name(
                payload.father_name, field="father_name", label="Father name"
            ),
            "province": province,
            "district": district,
            "tehsil": tehsil,
            "village": normalise_village(payload.village),
            "location_id": self._location_id(most_specific),
        }

    def _resolve_hemp(self, payload: FarmerIn, id_number_norm: str) -> dict[str, Any]:
        licence = normalise_licence_no(payload.home_office_licence_no)
        clash = self.farmers.get_by_licence_no(licence)
        if clash is not None and clash.id_number_norm != id_number_norm:
            raise ConflictError(
                f"That Home Office licence number is already recorded for SAWIE ID "
                f"{clash.sawie_id}.",
                code="farmer_duplicate_licence_no",
                details={"sawie_id": clash.sawie_id, "farmer_id": clash.id},
            )

        postcode = normalise_postcode(payload.postcode)
        resolved = PostcodeService(self.session).lookup(postcode)
        if resolved.resolved:
            county, region = resolved.county, resolved.region
        else:
            # The single case where the officer's own values are accepted.
            county = sanitise_text(payload.county)
            region = sanitise_text(payload.region)
            if not county or not region:
                raise self._required(
                    "county",
                    "The postcode could not be looked up. Enter the county and region.",
                )
        return {
            "farm_name": normalise_farm_name(payload.farm_name),
            "home_office_licence_no": licence,
            "postcode_norm": postcode,
            "county": county,
            "region": region,
        }

    @staticmethod
    def _required(field: str, message: str) -> ValidationAppError:
        return ValidationAppError(
            message,
            code="validation_error",
            details={"fields": [{"field": field, "location": "body", "message": message}]},
        )

    def _location_name(self, code: str | None, field: str, label: str) -> str:
        cleaned = sanitise_text(code)
        if not cleaned:
            raise self._required(field, f"{label} is required.")
        name = self.locations.resolve_name(cleaned)
        if name is None:
            raise self._required(field, f"Choose a {label.lower()} from the list.")
        return name

    def _location_id(self, code: str | None) -> str | None:
        cleaned = sanitise_text(code)
        if not cleaned:
            return None
        location = self.locations.locations.get_by_code(cleaned)
        return location.id if location else None

    # -------------------------------------------------------------------- reading

    def require_farmer(self, farmer_id: str) -> Farmer:
        farmer = self.farmers.get(farmer_id)
        if farmer is None:
            raise NotFoundError(
                "That farmer does not exist.",
                code="farmer_not_found",
                details={"farmer_id": farmer_id},
            )
        return farmer

    def search(
        self,
        params: PageParams,
        officer: CurrentOfficer,
        *,
        q: str | None = None,
        crop: str | None = None,
        field_office_id: str | None = None,
        registered_by: str | None = None,
    ) -> Page[FarmerListItemOut]:
        scope = self.scope_for(officer)
        result = self.farmers.search(
            params,
            q=q,
            crop=validate_crop(crop) if crop else None,
            field_office_id=field_office_id,
            registered_by=registered_by or scope,
        )
        rows = list(result.rows)
        counts = self.fields.counts_by_farmer([f.id for f in rows])
        return Page(
            items=[self.to_list_item(f, counts.get(f.id, 0)) for f in rows],
            total=result.total,
            page=params.page,
            page_size=params.page_size,
        )

    def profile(self, farmer_id: str, officer: CurrentOfficer) -> FarmerProfileOut:
        farmer = self.require_farmer(farmer_id)
        field_service = FieldService(self.session, bus=self.bus)
        fields = self.fields.list_for_farmer(farmer.id)
        total_m2 = sum(f.area_m2 for f in fields)
        missing: list[str] = []
        if not fields:
            missing.append("At least one mapped field")
        return FarmerProfileOut(
            farmer=self.to_out(farmer, officer),
            season_profiles=[
                SeasonProfileOut.model_validate(p) for p in self.profiles.list_for_farmer(farmer.id)
            ],
            fields=[field_service.to_out(f) for f in fields],
            completeness=FarmerCompletenessOut(
                has_fields=bool(fields),
                field_count=len(fields),
                total_area_acre=total_m2 / 4046.8564224,
                total_area_ha=total_m2 / 10_000.0,
                ready_for_fieldbook=bool(fields),
                missing=missing,
            ),
        )

    # ------------------------------------------------------------- presentation

    @staticmethod
    def _office_ref(office: Any) -> FieldOfficeRefOut | None:
        if office is None:
            return None
        return FieldOfficeRefOut(id=office.id, code=office.code, name=office.name)

    @staticmethod
    def _officer_ref(officer: Any) -> OfficerRefOut | None:
        if officer is None:
            return None
        return OfficerRefOut(id=officer.id, code=officer.code, full_name=officer.full_name)

    @staticmethod
    def location_summary(farmer: Farmer) -> str:
        if farmer.country == COUNTRY_GB:
            parts = [farmer.postcode_norm, farmer.county, farmer.region]
        else:
            parts = [farmer.village, farmer.tehsil, farmer.district]
        return ", ".join(p for p in parts if p) or "-"

    def to_list_item(self, farmer: Farmer, field_count: int) -> FarmerListItemOut:
        office = self.offices.get(farmer.field_office_id)
        registrar = self.officers.get(farmer.registered_by) if farmer.registered_by else None
        return FarmerListItemOut(
            id=farmer.id,
            sawie_id=farmer.sawie_id,
            crop=farmer.crop,  # type: ignore[arg-type]
            country=farmer.country,
            name=farmer.name,
            father_name=farmer.father_name,
            farm_name=farmer.farm_name,
            id_number_masked=mask_id_number(farmer.id_number_display),
            phone_masked=mask_phone(farmer.phone_display),
            location_summary=self.location_summary(farmer),
            field_office=self._office_ref(office),
            registered_by=self._officer_ref(registrar),
            field_count=field_count,
            has_fields=field_count > 0,
            created_at=farmer.created_at,
        )

    def to_out(self, farmer: Farmer, officer: CurrentOfficer | None) -> FarmerOut:
        visible = self.may_see_sensitive(farmer, officer)
        registrar = self.officers.get(farmer.registered_by) if farmer.registered_by else None
        return FarmerOut(
            id=farmer.id,
            sawie_id=farmer.sawie_id,
            crop=farmer.crop,  # type: ignore[arg-type]
            country=farmer.country,
            name=farmer.name,
            father_name=farmer.father_name,
            farm_name=farmer.farm_name,
            id_number=(
                farmer.id_number_display if visible else mask_id_number(farmer.id_number_display)
            ),
            phone=(farmer.phone_display if visible else mask_phone(farmer.phone_display)),
            sensitive_visible=visible,
            province=farmer.province,
            district=farmer.district,
            tehsil=farmer.tehsil,
            village=farmer.village,
            home_office_licence_no=farmer.home_office_licence_no,
            postcode=farmer.postcode_norm,
            county=farmer.county,
            region=farmer.region,
            field_office=self._office_ref(self.offices.get(farmer.field_office_id)),
            registered_by=self._officer_ref(registrar),
            created_at=farmer.created_at,
            updated_at=farmer.updated_at,
        )

    def _personal(self, farmer: Farmer) -> FarmerPersonalOut:
        """Personal data for pre-filling the form. No crop data, by design."""
        codes = self._location_codes(farmer)
        return FarmerPersonalOut(
            name=farmer.name,
            father_name=farmer.father_name,
            farm_name=farmer.farm_name,
            phone=farmer.phone_display,
            province_code=codes.get("province"),
            province=farmer.province,
            district_code=codes.get("district"),
            district=farmer.district,
            tehsil_code=codes.get("tehsil"),
            tehsil=farmer.tehsil,
            village=farmer.village,
            home_office_licence_no=farmer.home_office_licence_no,
            postcode=farmer.postcode_norm,
            county=farmer.county,
            region=farmer.region,
            field_office_id=farmer.field_office_id,
        )

    def _location_codes(self, farmer: Farmer) -> dict[str, str | None]:
        """Walk ``location_id`` up its parents so the cascade can be re-selected."""
        codes: dict[str, str | None] = {"province": None, "district": None, "tehsil": None}
        if not farmer.location_id:
            return codes
        current = self.locations.locations.get(farmer.location_id)
        while current is not None:
            if current.level in codes:
                codes[current.level] = current.code
            current = self.locations.locations.get(current.parent_id) if current.parent_id else None
        return codes


__all__ = ["FarmerService", "current_season_year"]
