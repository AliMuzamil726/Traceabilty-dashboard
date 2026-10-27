"""Two small sections: the officer overview and the guided checklist.

The officer overview is for administrators only, which the router enforces: it shows
what every officer has registered and submitted this season. The checklist is the
dashboard's empty state, and it adapts to the officer's role, because an administrator
is not the person who registers farmers.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from core.deps import CurrentOfficer
from module_1.services import links, sources
from module_1.services.filters import DashboardFilters
from shared.repositories.officers import OfficerRepository
from shared.repositories.offices import FieldOfficeRepository


def build_officer_overview(session: Session, f: DashboardFilters) -> dict[str, Any]:
    """Every active officer with their registration and fieldbook work this season."""
    officers = OfficerRepository(session).list_all()
    offices = {o.id: o.name for o in FieldOfficeRepository(session).list_all()}
    registrations = sources.officer_registrations(session, f)
    submitted = sources.submitted_by_officer(session, f)
    items = []
    for officer in officers:
        row = registrations.get(officer.id)
        items.append(
            {
                "officer_id": officer.id,
                "code": officer.code,
                "full_name": officer.full_name,
                "role": officer.role,
                "country": officer.country,
                "field_office_name": offices.get(officer.field_office_id or ""),
                "farmers": row.farmers if row else 0,
                "fields": row.fields if row else 0,
                "area": (
                    (row.area_acre if f.area_unit() == "acre" else row.area_ha) if row else 0.0
                ),
                "fieldbooks_submitted": submitted.get(officer.id, 0),
            }
        )
    items.sort(key=lambda r: (-r["farmers"], str(r["full_name"])))
    return {
        "crop": f.crop,
        "season_year": f.season_year,
        "area_unit": f.area_unit(),
        "items": items,
        "generated_at": datetime.now(UTC),
    }


def build_onboarding(
    session: Session, f: DashboardFilters, officer: CurrentOfficer
) -> dict[str, Any]:
    """The Get started checklist, and whether the dashboard has anything to show.

    Deliberately cheap: three counts, no readiness dataset. An administrator sees the
    programme's figures and is pointed at the officers' work rather than told to
    register a farmer themselves.
    """
    registration = sources.registration_view(session, f, officer)
    books = sources.fieldbook_counts(session, f)
    started = books["draft"] + books["submitted"]
    mine = not officer.sees_all

    steps = [
        {
            "key": "register_farmer",
            "title": "Register your first farmer" if mine else "Register the first farmer",
            "description": (
                "Pick the crop programme, enter the ID number and save. The SAWIE ID is "
                "allocated for life."
            ),
            "done": registration.farmers > 0,
            "count": registration.farmers,
            "link": links.register(f).as_dict(),
        },
        {
            "key": "map_field",
            "title": "Map a field",
            "description": (
                "Draw the boundary on the satellite map. Nothing downstream can start "
                "until a farmer has one field."
            ),
            "done": registration.fields > 0,
            "count": registration.fields,
            "link": links.register(f).as_dict(),
        },
        {
            "key": "open_fieldbook",
            "title": "Open a fieldbook",
            "description": (
                "The field's season diary. It feeds the crop clock, Harvest Radar and "
                "every figure after it."
            ),
            "done": started > 0,
            "count": started,
            "link": links.fieldbook_list().as_dict(),
        },
    ]
    return {
        "is_empty": registration.farmers == 0,
        "role": officer.role,
        "scope": f.scope,
        "crop": f.crop,
        "season_year": f.season_year,
        "counts": {
            "farmers": registration.farmers,
            "fields": registration.fields,
            "fieldbooks": started,
        },
        "steps": steps,
        "generated_at": datetime.now(UTC),
    }


__all__ = ["build_officer_overview", "build_onboarding"]
