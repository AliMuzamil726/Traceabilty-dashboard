"""The only place Module 1 reads other modules.

Every figure on the dashboard comes from a function here, and every function here is a
call to another module's ``public_api``. Module 1 owns no tables and never touches
another module's, so this file is the whole data layer of the dashboard.

Each loader takes the filters and the acting officer and applies the crop and scope
choices once, so two sections can never disagree about what "my cotton this season"
means.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime

from sqlalchemy.orm import Session

from core.deps import CurrentOfficer
from module_1 import config
from module_1.services.filters import DashboardFilters, DateRange
from module_2 import public_api as farms
from module_3 import public_api as fieldbooks
from module_4 import public_api as radar
from module_5 import public_api as deliveries
from module_6 import public_api as heaps
from module_7 import public_api as qr

# ------------------------------------------------------------------- fields (2,3,4)


def readiness_rows(
    session: Session,
    f: DashboardFilters,
    officer: CurrentOfficer,
    *,
    include_geometry: bool = False,
) -> list[radar.ReadinessRowDTO]:
    """Every mapped field in the filter, with its readiness and fieldbook state.

    This is Harvest Radar's own dataset (``module_4.public_api.list_readiness_rows``),
    which is why the dashboard's field counts reconcile with the radar exactly. One
    call per crop programme, cached inside Module 4 for 30 seconds.
    """
    officer_id = f.officer_filter(officer)
    rows: list[radar.ReadinessRowDTO] = []
    for crop in f.crops:
        rows += radar.list_readiness_rows(
            session,
            crop=crop,
            season_year=f.season_year,
            officer_id=officer_id,
            include_geometry=include_geometry,
        )
    return rows


# -------------------------------------------------------------- registrations (2)


@dataclass(frozen=True)
class RegistrationView:
    """Farmer and field counts narrowed to the filter's crops."""

    farmers: int
    farmers_by_crop: dict[str, int]
    fields: int
    fields_by_crop: dict[str, int]
    area: float
    area_by_crop: dict[str, float]
    area_unit: str


def registration_view(
    session: Session, f: DashboardFilters, officer: CurrentOfficer
) -> RegistrationView:
    """Farmers, fields and mapped area for the filter, in the crop's own area unit."""
    totals = farms.get_registration_totals(session, registered_by=f.officer_filter(officer))
    area_by_crop = {
        crop: (
            totals.area_acre_by_crop if config.AREA_UNIT[crop] == "acre" else totals.area_ha_by_crop
        )[crop]
        for crop in f.crops
    }
    return RegistrationView(
        farmers=sum(totals.farmers_by_crop[c] for c in f.crops),
        farmers_by_crop={c: totals.farmers_by_crop[c] for c in f.crops},
        fields=sum(totals.fields_by_crop[c] for c in f.crops),
        fields_by_crop={c: totals.fields_by_crop[c] for c in f.crops},
        area=round(sum(area_by_crop.values()), 2),
        area_by_crop=area_by_crop,
        area_unit=f.area_unit(),
    )


def farmers_without_field(
    session: Session, f: DashboardFilters, officer: CurrentOfficer
) -> tuple[int, list[farms.FarmerRefDTO]]:
    """How many farmers have no mapped field, and the newest few of them."""
    officer_id = f.officer_filter(officer)
    count = 0
    samples: list[farms.FarmerRefDTO] = []
    for crop in f.crops:
        count += farms.count_farmers_without_field(session, crop=crop, registered_by=officer_id)
        samples += farms.list_farmers_without_field(
            session, crop=crop, registered_by=officer_id, limit=config.ALERT_SAMPLE_LIMIT
        )
    samples.sort(key=lambda s: (s.registered_at or datetime.min.replace(tzinfo=None)), reverse=True)
    return count, samples[: config.ALERT_SAMPLE_LIMIT]


def registration_times(
    session: Session,
    f: DashboardFilters,
    officer: CurrentOfficer,
    *,
    crop: str,
    window: DateRange,
) -> list[datetime]:
    """When each farmer of one crop was registered inside the range."""
    return farms.registration_times(
        session,
        crop=crop,
        registered_by=f.officer_filter(officer),
        since=window.since,
        until=window.until,
    )


def field_mapped_times(
    session: Session,
    f: DashboardFilters,
    officer: CurrentOfficer,
    *,
    crop: str,
    window: DateRange,
) -> list[datetime]:
    """When each field of one crop was mapped inside the range."""
    return farms.field_mapped_times(
        session,
        crop=crop,
        registered_by=f.officer_filter(officer),
        since=window.since,
        until=window.until,
    )


def region_areas(
    session: Session, f: DashboardFilters, officer: CurrentOfficer, *, crop: str
) -> list[farms.RegionAreaDTO]:
    """Mapped area by district (cotton) or county (hemp), largest first."""
    return farms.area_by_region(
        session,
        crop=crop,
        registered_by=f.officer_filter(officer),
        limit=config.TOP_REGIONS,
    )


def officer_registrations(
    session: Session, f: DashboardFilters
) -> dict[str, farms.OfficerRegistrationsDTO]:
    """Farmers and fields per officer across the filter's crops."""
    out: dict[str, farms.OfficerRegistrationsDTO] = {}
    for crop in f.crops:
        for officer_id, row in farms.registrations_by_officer(session, crop=crop).items():
            seen = out.get(officer_id)
            out[officer_id] = farms.OfficerRegistrationsDTO(
                officer_id=officer_id,
                farmers=row.farmers + (seen.farmers if seen else 0),
                fields=row.fields + (seen.fields if seen else 0),
                area_acre=round(row.area_acre + (seen.area_acre if seen else 0.0), 2),
                area_ha=round(row.area_ha + (seen.area_ha if seen else 0.0), 2),
            )
    return out


def submitted_by_officer(session: Session, f: DashboardFilters) -> dict[str, int]:
    """Fieldbooks submitted this season per officer, across the filter's crops."""
    out: dict[str, int] = {}
    for crop in f.crops:
        counts = fieldbooks.count_submitted_by_officer(
            session, crop=crop, season_year=f.season_year
        )
        for officer_id, count in counts.items():
            out[officer_id] = out.get(officer_id, 0) + count
    return out


def farmer_ids_for_officer(session: Session, officer_id: str) -> set[str]:
    """The farmers an officer registered; the key to scoping deliveries to their work."""
    return {farmer.id for farmer in farms.list_farmers_for_officer(session, officer_id)}


# ---------------------------------------------------------------- deliveries (5)


def delivery_totals(
    session: Session,
    f: DashboardFilters,
    officer: CurrentOfficer,
    *,
    window: DateRange | None = None,
) -> deliveries.DeliveryTotalsDTO:
    """Delivery counts and delivered quantity for the filter, added across its crops.

    ``window`` narrows the delivered figures to the loads weighed in during the range,
    which is what "delivered in the last 30 days" means. The status counts always cover
    the whole season, so a short range never hides a delivery still on its way.
    """
    farmer_ids = _scoped_farmer_ids(session, f, officer)
    by_status: dict[str, int] = {}
    delivered = flags = 0
    kg = moisture_weighted = 0.0
    moisture_n = 0
    for crop in f.crops:
        totals = deliveries.get_delivery_totals(
            session,
            deliveries.DeliveryQuery(
                crop=crop,
                farmer_ids=farmer_ids,
                season_year=f.season_year,
                delivered_from=window.since if window else None,
                delivered_to=window.until if window else None,
            ),
        )
        for status, count in totals.by_status.items():
            by_status[status] = by_status.get(status, 0) + count
        delivered += totals.delivered
        kg += totals.delivered_kg
        flags += totals.weight_flags
        if totals.average_moisture_pct is not None and totals.delivered:
            moisture_weighted += totals.average_moisture_pct * totals.delivered
            moisture_n += totals.delivered
    return deliveries.DeliveryTotalsDTO(
        total=sum(by_status.values()),
        by_status=by_status,
        delivered=delivered,
        delivered_kg=round(kg, 1),
        delivered_maunds=round(kg / 40, 2),
        average_moisture_pct=(
            None if moisture_n == 0 else round(moisture_weighted / moisture_n, 2)
        ),
        weight_flags=flags,
    )


def delivered_rows(
    session: Session,
    f: DashboardFilters,
    officer: CurrentOfficer,
    window: DateRange,
) -> list[tuple[datetime, float, float | None]]:
    """``(delivered_at, kg, moisture)`` for every delivery received inside the range."""
    farmer_ids = _scoped_farmer_ids(session, f, officer)
    rows: list[tuple[datetime, float, float | None]] = []
    for crop in f.crops:
        rows += deliveries.delivered_rows_in_range(
            session,
            crop=crop,
            farmer_ids=farmer_ids,
            season_year=f.season_year,
            delivered_from=window.since,
            delivered_to=window.until,
        )
    return sorted(rows, key=lambda r: r[0])


def delivery_alert(
    session: Session,
    f: DashboardFilters,
    officer: CurrentOfficer,
    *,
    statuses: tuple[str, ...] | None = None,
    date_to: date | None = None,
    variance_level: str | None = None,
    samples: int = config.ALERT_SAMPLE_LIMIT,
) -> tuple[int, list[deliveries.DeliveryDTO]]:
    """``(count, a few examples)`` for one delivery alert rule.

    The count is a SQL count and only the examples are loaded, so a long backlog costs
    the same as a short one.
    """
    farmer_ids = _scoped_farmer_ids(session, f, officer)
    total = 0
    rows: list[deliveries.DeliveryDTO] = []
    for crop in f.crops:
        query = deliveries.DeliveryQuery(
            crop=crop,
            statuses=statuses,
            season_year=f.season_year,
            date_to=date_to,
            variance_level=variance_level,
            farmer_ids=farmer_ids,
        )
        total += deliveries.count_deliveries(session, query)
        rows += deliveries.list_deliveries(session, replace(query, limit=samples))
    return total, rows


def _scoped_farmer_ids(
    session: Session, f: DashboardFilters, officer: CurrentOfficer
) -> tuple[str, ...] | None:
    officer_id = f.officer_filter(officer)
    if officer_id is None:
        return None
    return tuple(sorted(farmer_ids_for_officer(session, officer_id)))


# -------------------------------------------------------------------- heaps (6)


def heap_rows(session: Session, f: DashboardFilters) -> list[heaps.HeapActivityDTO]:
    """Every heap or batch of the filter's crops, with its utilisation and last activity.

    Heaps belong to a site and a crop, not to an officer or a season: a heap mixes many
    farmers' crop, so it is never narrowed by scope (D-101).
    """
    rows: list[heaps.HeapActivityDTO] = []
    for crop in f.crops:
        rows += heaps.list_heap_activity(session, crop=crop)
    return rows


def bale_count(session: Session, f: DashboardFilters, *, window: DateRange | None = None) -> int:
    """Active bales, optionally only those made inside the range."""
    return sum(
        heaps.count_bales(
            session,
            crop=crop,
            since=window.since if window else None,
            until=window.until if window else None,
        )
        for crop in f.crops
    )


# ----------------------------------------------------------------------- codes (7)


def scan_totals(
    session: Session, f: DashboardFilters, *, window: DateRange | None = None
) -> qr.ScanTotalsDTO:
    """Scan counts and live codes for the filter's crops, added together."""
    total = public = internal = active = 0
    last: datetime | None = None
    for crop in f.crops:
        row = qr.get_scan_totals(
            session,
            crop=crop,
            since=window.since if window else None,
            until=window.until if window else None,
        )
        total += row.total
        public += row.public
        internal += row.internal
        active += row.active_tokens
        if row.last_scan_at is not None and (last is None or row.last_scan_at > last):
            last = row.last_scan_at
    return qr.ScanTotalsDTO(
        total=total, public=public, internal=internal, last_scan_at=last, active_tokens=active
    )


# ------------------------------------------------------------------ fieldbooks (3)


def fieldbook_counts(session: Session, f: DashboardFilters) -> dict[str, int]:
    """Draft and submitted fieldbooks for the filter's crops and season.

    Used by the empty-state check, which must stay cheap; every other fieldbook figure
    on the dashboard comes from :func:`readiness_rows`, so it reconciles with Radar.
    """
    out = {"draft": 0, "submitted": 0}
    for crop in f.crops:
        counts = fieldbooks.count_fieldbooks_by_status(
            session, crop=crop, season_year=f.season_year
        )
        out["draft"] += counts["draft"]
        out["submitted"] += counts["submitted"]
    return out


def step_completion(
    session: Session, f: DashboardFilters, crop: str
) -> list[fieldbooks.StepCompletionDTO]:
    """How far the season's fieldbooks have got with each step of one crop's form."""
    return fieldbooks.count_step_completion(session, crop=crop, season_year=f.season_year)


def stale_drafts(
    session: Session, f: DashboardFilters, *, updated_before: datetime
) -> list[fieldbooks.StaleDraftDTO]:
    out: list[fieldbooks.StaleDraftDTO] = []
    for crop in f.crops:
        out += fieldbooks.list_stale_drafts(
            session, updated_before=updated_before, crop=crop, season_year=f.season_year
        )
    return out


def licence_expiries(session: Session, f: DashboardFilters) -> list[fieldbooks.LicenceExpiryDTO]:
    """Hemp licence expiry dates; empty when the filter has no hemp in it."""
    if "hemp" not in f.crops:
        return []
    return fieldbooks.list_licence_expiries(session, season_year=f.season_year)


__all__ = [
    "RegistrationView",
    "bale_count",
    "delivered_rows",
    "delivery_alert",
    "delivery_totals",
    "farmer_ids_for_officer",
    "farmers_without_field",
    "field_mapped_times",
    "fieldbook_counts",
    "heap_rows",
    "licence_expiries",
    "officer_registrations",
    "readiness_rows",
    "region_areas",
    "registration_times",
    "registration_view",
    "scan_totals",
    "stale_drafts",
    "step_completion",
    "submitted_by_officer",
]
