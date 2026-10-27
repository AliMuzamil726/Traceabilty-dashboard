"""HTTP routes for Module 8 (Settings), mounted at ``/api/v1/settings``.

Two access rules run through the whole file:

* everything is administrator-only, enforced by
  :func:`core.permissions.require` with the ``settings.manage`` capability, except
* ``GET|PUT /me/preferences`` and ``GET /public``, which every officer uses. The
  preferences routes read the acting officer from the request, so an officer can only
  ever reach their own row.

Every write is audited by the service that performs it and publishes ``config.changed``
(or the more specific ``list.changed`` / ``location.changed``) so caches drop what they
hold and open screens refresh.
"""

from __future__ import annotations

import io
from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path, Query, Request, Response
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session

from core import permissions
from core.config import Settings
from core.deps import CurrentOfficer, get_current_officer, get_db, get_settings_dep
from module_8 import meta, registry
from module_8.schemas import (
    AuditFacetsOut,
    AuditPageOut,
    BackupIn,
    BackupOut,
    BackupStatusOut,
    ConfigIn,
    DummyDataOut,
    DummyRemovedOut,
    ImportReportOut,
    ListSummaryOut,
    ListValueIn,
    ListValueOut,
    ListValueUpdateIn,
    LocationIn,
    LocationTreeOut,
    LocationUpdateIn,
    MergeIn,
    OfficeIn,
    OfficeOut,
    OfficerIn,
    OfficerOut,
    OfficerUpdateIn,
    OfficeUpdateIn,
    PermissionRowOut,
    PreferencesIn,
    PreferencesOut,
    PublicConfigOut,
    ReorderIn,
    RestoreIn,
    RestoreOut,
    SettingIn,
    SettingOut,
    SettingsPageOut,
    SiteIn,
    SiteOut,
    SiteUpdateIn,
    SystemOut,
    TestResultOut,
    TestTilesIn,
    TestUrlIn,
)
from module_8.services.audit_log import AuditService
from module_8.services.backups import BackupService
from module_8.services.config import ConfigService
from module_8.services.lists import ListService
from module_8.services.locations import LocationService
from module_8.services.people import OfficerService, OfficeService
from module_8.services.preferences import PreferenceService
from module_8.services.public_config import check_public_url, check_tiles, public_config
from module_8.services.sites import SiteService
from module_8.services.system import SystemService
from module_8.services.values import SettingsValueService
from shared.schemas import ModuleMetaOut

router = APIRouter(prefix=meta.API_PREFIX, tags=[f"module_{meta.NUMBER}"])


#: Dependency: the acting officer, refused unless they are an administrator.
def admin(officer: CurrentOfficer = Depends(get_current_officer)) -> CurrentOfficer:
    permissions.require(officer, "settings.manage")
    return officer


Admin = Annotated[CurrentOfficer, Depends(admin)]
Officer = Annotated[CurrentOfficer, Depends(get_current_officer)]
Db = Annotated[Session, Depends(get_db)]

KEY = Path(..., max_length=80, description="Setting key, for example map.tile_provider")


def _csv(text: str, filename: str) -> StreamingResponse:
    """A CSV download with the BOM Excel needs to read UTF-8 correctly."""
    return StreamingResponse(
        io.BytesIO(("﻿" + text).encode("utf-8")),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/meta", response_model=ModuleMetaOut, summary="Module identity and build status")
def module_meta() -> ModuleMetaOut:
    return ModuleMetaOut(
        number=meta.NUMBER,
        name=meta.NAME,
        status=meta.STATUS,
        route_prefix=meta.ROUTE_PREFIX,
        api_prefix=meta.API_PREFIX,
        purpose=meta.PURPOSE,
        build_order=meta.BUILD_ORDER,
    )


# ---------------------------------------------------------------- public config


@router.get(
    "/public",
    response_model=PublicConfigOut,
    summary="Configuration the web app needs before it draws a screen (no secrets)",
)
def get_public_config(response: Response, session: Db) -> PublicConfigOut:
    data = public_config(session)
    response.headers["Cache-Control"] = f"public, max-age={data['cache_seconds']}"
    return PublicConfigOut(**data)


# ------------------------------------------------------------- generic settings


@router.get("/registry", response_model=SettingsPageOut, summary="Every declared setting")
def get_registry(session: Db, _: Admin, group: str | None = Query(None)) -> SettingsPageOut:
    service = SettingsValueService(session)
    items = [SettingOut(**view.as_dict()) for view in service.list_all(group)]
    return SettingsPageOut(items=items, groups=list(registry.GROUPS))


@router.get("/values/{key}", response_model=SettingOut, summary="One setting")
def get_value(session: Db, _: Admin, key: str = KEY) -> SettingOut:
    return SettingOut(**SettingsValueService(session).get(key).as_dict())


@router.put("/values/{key}", response_model=SettingOut, summary="Change one setting")
def put_value(session: Db, officer: Admin, body: SettingIn, key: str = KEY) -> SettingOut:
    view = SettingsValueService(session).set(
        key,
        body.value,
        officer,
        expected_version=body.expected_version,
        reason=body.reason,
    )
    return SettingOut(**view.as_dict())


@router.delete(
    "/values/{key}", response_model=SettingOut, summary="Drop the override, back to the default"
)
def reset_value(session: Db, officer: Admin, key: str = KEY) -> SettingOut:
    return SettingOut(**SettingsValueService(session).reset(key, officer).as_dict())


@router.get("/history", summary="Recent changes, newest first")
def get_history(
    session: Db,
    _: Admin,
    key: str | None = Query(None, max_length=80),
    limit: int = Query(50, ge=1, le=200),
) -> list[dict[str, Any]]:
    return SettingsValueService(session).history_for(key, limit)


@router.post("/history/{history_id}/restore", response_model=SettingOut, summary="Put a value back")
def restore_history(
    session: Db, officer: Admin, history_id: str = Path(..., max_length=36)
) -> SettingOut:
    return SettingOut(**SettingsValueService(session).restore(history_id, officer).as_dict())


# ---------------------------------------------------------------------- people


@router.get("/officers", response_model=list[OfficerOut], summary="Officers")
def list_officers(
    session: Db,
    _: Admin,
    active: bool | None = Query(None),
    office_id: str | None = Query(None, max_length=36),
    q: str | None = Query(None, max_length=120, description="Name or code"),
) -> list[OfficerOut]:
    rows = OfficerService(session).list_officers(active=active, office_id=office_id, q=q)
    return [OfficerOut(**row) for row in rows]


@router.post("/officers", response_model=OfficerOut, status_code=201, summary="Add an officer")
def create_officer(session: Db, officer: Admin, body: OfficerIn) -> OfficerOut:
    return OfficerOut(**OfficerService(session).create(body.model_dump(exclude_none=True), officer))


@router.get("/officers/export.csv", summary="Officers as CSV")
def export_officers(session: Db, _: Admin) -> StreamingResponse:
    return _csv(OfficerService(session).export_csv(), "sawie-officers.csv")


@router.post("/officers/import", response_model=ImportReportOut, summary="Import officers from CSV")
async def import_officers(
    session: Db,
    officer: Admin,
    request: Request,
    dry_run: bool = Query(True, description="Check the file without saving anything"),
) -> ImportReportOut:
    text = (await request.body()).decode("utf-8-sig", errors="replace")
    report = OfficerService(session).import_csv(text, officer, dry_run=dry_run)
    return ImportReportOut(**report.as_dict())


@router.get("/officers/{officer_id}", response_model=OfficerOut, summary="One officer")
def get_officer(session: Db, _: Admin, officer_id: str = Path(..., max_length=36)) -> OfficerOut:
    return OfficerOut(**OfficerService(session).get(officer_id))


@router.put("/officers/{officer_id}", response_model=OfficerOut, summary="Change an officer")
def update_officer(
    session: Db, officer: Admin, body: OfficerUpdateIn, officer_id: str = Path(..., max_length=36)
) -> OfficerOut:
    data = body.model_dump(exclude_unset=True)
    return OfficerOut(**OfficerService(session).update(officer_id, data, officer))


@router.post(
    "/officers/{officer_id}/deactivate", response_model=OfficerOut, summary="Deactivate an officer"
)
def deactivate_officer(
    session: Db, officer: Admin, officer_id: str = Path(..., max_length=36)
) -> OfficerOut:
    return OfficerOut(**OfficerService(session).set_active(officer_id, False, officer))


@router.post(
    "/officers/{officer_id}/activate", response_model=OfficerOut, summary="Activate an officer"
)
def activate_officer(
    session: Db, officer: Admin, officer_id: str = Path(..., max_length=36)
) -> OfficerOut:
    return OfficerOut(**OfficerService(session).set_active(officer_id, True, officer))


@router.get("/offices", response_model=list[OfficeOut], summary="Field offices")
def list_offices(session: Db, _: Admin, active: bool | None = Query(None)) -> list[OfficeOut]:
    return [OfficeOut(**row) for row in OfficeService(session).list_offices(active=active)]


@router.post("/offices", response_model=OfficeOut, status_code=201, summary="Add a field office")
def create_office(session: Db, officer: Admin, body: OfficeIn) -> OfficeOut:
    return OfficeOut(**OfficeService(session).create(body.model_dump(exclude_none=True), officer))


@router.put("/offices/{office_id}", response_model=OfficeOut, summary="Change a field office")
def update_office(
    session: Db, officer: Admin, body: OfficeUpdateIn, office_id: str = Path(..., max_length=36)
) -> OfficeOut:
    data = body.model_dump(exclude_unset=True)
    return OfficeOut(**OfficeService(session).update(office_id, data, officer))


# ----------------------------------------------------------------------- sites


@router.get("/sites", response_model=list[SiteOut], summary="Ginners and processors")
def list_sites(
    session: Db, _: Admin, crop: str | None = Query(None), active: bool | None = Query(None)
) -> list[SiteOut]:
    return [SiteOut(**row) for row in SiteService(session).list_sites(crop=crop, active=active)]


@router.post("/sites", response_model=SiteOut, status_code=201, summary="Add a site")
def create_site(session: Db, officer: Admin, body: SiteIn) -> SiteOut:
    return SiteOut(**SiteService(session).create(body.model_dump(exclude_none=True), officer))


@router.put("/sites/{site_id}", response_model=SiteOut, summary="Change a site")
def update_site(
    session: Db, officer: Admin, body: SiteUpdateIn, site_id: str = Path(..., max_length=36)
) -> SiteOut:
    data = body.model_dump(exclude_unset=True)
    return SiteOut(**SiteService(session).update(site_id, data, officer))


@router.delete("/sites/{site_id}", status_code=204, summary="Delete an unused site")
def delete_site(session: Db, officer: Admin, site_id: str = Path(..., max_length=36)) -> Response:
    SiteService(session).delete(site_id, officer)
    return Response(status_code=204)


# ------------------------------------------------------------------- lists


@router.get("/lists", response_model=list[ListSummaryOut], summary="Dropdown lists")
def get_lists(session: Db, _: Admin) -> list[ListSummaryOut]:
    return [ListSummaryOut(**row) for row in ListService(session).list_lists()]


@router.get(
    "/lists/{list_key}/values", response_model=list[ListValueOut], summary="Values of one list"
)
def get_list_values(
    session: Db, _: Admin, list_key: str = Path(..., max_length=64)
) -> list[ListValueOut]:
    return [ListValueOut(**row) for row in ListService(session).values_for(list_key)]


@router.post(
    "/lists/{list_key}/values",
    response_model=ListValueOut,
    status_code=201,
    summary="Add a value",
)
def add_list_value(
    session: Db, officer: Admin, body: ListValueIn, list_key: str = Path(..., max_length=64)
) -> ListValueOut:
    data = body.model_dump(exclude_none=True)
    return ListValueOut(**ListService(session).add_value(list_key, data, officer))


@router.put(
    "/lists/{list_key}/values/{value_id}", response_model=ListValueOut, summary="Edit a value"
)
def update_list_value(
    session: Db,
    officer: Admin,
    body: ListValueUpdateIn,
    list_key: str = Path(..., max_length=64),
    value_id: str = Path(..., max_length=36),
) -> ListValueOut:
    data = body.model_dump(exclude_unset=True)
    return ListValueOut(**ListService(session).update_value(value_id, data, officer))


@router.delete(
    "/lists/{list_key}/values/{value_id}", status_code=204, summary="Delete an unused value"
)
def delete_list_value(
    session: Db,
    officer: Admin,
    list_key: str = Path(..., max_length=64),
    value_id: str = Path(..., max_length=36),
) -> Response:
    ListService(session).delete_value(value_id, officer)
    return Response(status_code=204)


@router.post(
    "/lists/{list_key}/reorder", response_model=list[ListValueOut], summary="Save a new order"
)
def reorder_list(
    session: Db, officer: Admin, body: ReorderIn, list_key: str = Path(..., max_length=64)
) -> list[ListValueOut]:
    rows = ListService(session).reorder(list_key, body.ids, officer)
    return [ListValueOut(**row) for row in rows]


@router.get("/lists/{list_key}/export.csv", summary="One list as CSV")
def export_list(
    session: Db, _: Admin, list_key: str = Path(..., max_length=64)
) -> StreamingResponse:
    return _csv(ListService(session).export_csv(list_key), f"sawie-{list_key}.csv")


@router.post("/lists/{list_key}/import", summary="Import list values from CSV")
async def import_list(
    session: Db,
    officer: Admin,
    request: Request,
    list_key: str = Path(..., max_length=64),
    dry_run: bool = Query(True, description="Check the file without saving anything"),
) -> dict[str, Any]:
    text = (await request.body()).decode("utf-8-sig", errors="replace")
    return ListService(session).import_csv(list_key, text, officer, dry_run=dry_run)


# ------------------------------------------------------------------- locations


@router.get("/locations/tree", response_model=LocationTreeOut, summary="Locations as a tree")
def locations_tree(
    session: Db, _: Admin, country: str = Query("PK", max_length=2)
) -> LocationTreeOut:
    return LocationTreeOut(**LocationService(session).tree(country))


@router.post("/locations", status_code=201, summary="Add a location")
def create_location(session: Db, officer: Admin, body: LocationIn) -> dict[str, Any]:
    return LocationService(session).create(body.model_dump(exclude_none=True), officer)


@router.put("/locations/{location_id}", summary="Rename or deactivate a location")
def update_location(
    session: Db, officer: Admin, body: LocationUpdateIn, location_id: str = Path(..., max_length=36)
) -> dict[str, Any]:
    service = LocationService(session)
    data = body.model_dump(exclude_unset=True)
    result: dict[str, Any] = {}
    if data.get("name"):
        result = service.rename(location_id, data["name"], officer)
    if "active" in data and data["active"] is not None:
        result = service.set_active(location_id, bool(data["active"]), officer)
    return result or service.preview_rename(location_id, "")


@router.get("/locations/{location_id}/rename-preview", summary="What a rename would touch")
def preview_rename(
    session: Db,
    _: Admin,
    location_id: str = Path(..., max_length=36),
    name: str = Query("", max_length=120),
) -> dict[str, Any]:
    return LocationService(session).preview_rename(location_id, name)


@router.delete("/locations/{location_id}", status_code=204, summary="Delete an unused location")
def delete_location(
    session: Db, officer: Admin, location_id: str = Path(..., max_length=36)
) -> Response:
    LocationService(session).delete(location_id, officer)
    return Response(status_code=204)


@router.post("/locations/merge-preview", summary="What a merge would touch")
def preview_merge(session: Db, _: Admin, body: MergeIn) -> dict[str, Any]:
    return LocationService(session).preview_merge(body.source_id, body.target_id)


@router.post("/locations/merge", summary="Merge one location into another")
def merge_locations(session: Db, officer: Admin, body: MergeIn) -> dict[str, Any]:
    return LocationService(session).merge(body.source_id, body.target_id, officer)


@router.get("/locations/export.csv", summary="Locations as CSV")
def export_locations(
    session: Db, _: Admin, country: str = Query("PK", max_length=2)
) -> StreamingResponse:
    return _csv(LocationService(session).export_csv(country), f"sawie-locations-{country}.csv")


@router.post("/locations/import", summary="Import locations from CSV")
async def import_locations(
    session: Db,
    officer: Admin,
    request: Request,
    dry_run: bool = Query(True, description="Check the file without saving anything"),
) -> dict[str, Any]:
    text = (await request.body()).decode("utf-8-sig", errors="replace")
    return LocationService(session).import_csv(text, officer, dry_run=dry_run)


# -------------------------------------------------------------- owned config


@router.get("/config/{block}", summary="Configuration owned by another module")
def get_config(session: Db, _: Admin, block: str = Path(..., max_length=20)) -> dict[str, Any]:
    return ConfigService(session).get(block)


@router.put("/config/{block}", summary="Change configuration through its owning module")
def put_config(
    session: Db, officer: Admin, body: ConfigIn, block: str = Path(..., max_length=20)
) -> dict[str, Any]:
    return ConfigService(session).update(block, body.values, officer, body.expected_version)


@router.post("/config/clock/preview", summary="Fields that would change bucket")
def preview_clock(session: Db, _: Admin, body: ConfigIn) -> dict[str, Any]:
    return ConfigService(session).preview("clock", body.values)


# ----------------------------------------------------------------- permissions


@router.get("/permissions", response_model=list[PermissionRowOut], summary="What each role may do")
def get_permissions(_: Admin) -> list[PermissionRowOut]:
    return [PermissionRowOut(**row) for row in permissions.matrix()]


# ------------------------------------------------------------------- audit log


@router.get("/audit", response_model=AuditPageOut, summary="Search the audit log")
def get_audit(
    session: Db,
    _: Admin,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    module: int | None = Query(None, ge=1, le=8),
    entity: str | None = Query(None, max_length=64),
    entity_id: str | None = Query(None, max_length=64),
    officer_id: str | None = Query(None, max_length=36),
    action: str | None = Query(None, max_length=32),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
) -> AuditPageOut:
    data = AuditService(session).search(
        page=page,
        page_size=page_size,
        module=module,
        entity=entity,
        entity_id=entity_id,
        officer_id=officer_id,
        action=action,
        date_from=date_from,
        date_to=date_to,
    )
    return AuditPageOut(**data)


@router.get("/audit/facets", response_model=AuditFacetsOut, summary="Values present in the log")
def get_audit_facets(session: Db, _: Admin) -> AuditFacetsOut:
    return AuditFacetsOut(**AuditService(session).facets())


@router.get("/audit/export.csv", summary="The filtered audit log as CSV")
def export_audit(
    session: Db,
    _: Admin,
    module: int | None = Query(None, ge=1, le=8),
    entity: str | None = Query(None, max_length=64),
    officer_id: str | None = Query(None, max_length=36),
    action: str | None = Query(None, max_length=32),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
) -> StreamingResponse:
    text = AuditService(session).export_csv(
        module=module,
        entity=entity,
        officer_id=officer_id,
        action=action,
        date_from=date_from,
        date_to=date_to,
    )
    return _csv(text, "sawie-audit.csv")


# --------------------------------------------------------------------- backups


@router.get("/backups/status", response_model=BackupStatusOut, summary="Can backups be taken here")
def backup_status(session: Db, _: Admin) -> BackupStatusOut:
    return BackupStatusOut(**BackupService(session).status())


@router.get("/backups", response_model=list[BackupOut], summary="Backups on disk")
def list_backups(session: Db, _: Admin) -> list[BackupOut]:
    return [BackupOut(**row) for row in BackupService(session).list_backups()]


@router.post("/backups", response_model=BackupOut, status_code=201, summary="Take a backup now")
def create_backup(session: Db, officer: Admin, body: BackupIn) -> BackupOut:
    return BackupOut(**BackupService(session).create(officer, body.note))


@router.get("/backups/{backup_id}/download", summary="Download a backup file")
def download_backup(
    session: Db, _: Admin, backup_id: str = Path(..., max_length=36)
) -> FileResponse:
    record, path = BackupService(session).file_for(backup_id)
    return FileResponse(path, media_type="application/octet-stream", filename=record.filename)


@router.post("/backups/{backup_id}/restore", response_model=RestoreOut, summary="Restore a backup")
def restore_backup(
    session: Db, officer: Admin, body: RestoreIn, backup_id: str = Path(..., max_length=36)
) -> RestoreOut:
    return RestoreOut(**BackupService(session).restore(backup_id, body.confirm, officer))


@router.delete("/backups/{backup_id}", status_code=204, summary="Delete a backup file")
def delete_backup(
    session: Db, officer: Admin, backup_id: str = Path(..., max_length=36)
) -> Response:
    BackupService(session).delete(backup_id, officer)
    return Response(status_code=204)


# ---------------------------------------------------------------------- system


@router.get("/system", response_model=SystemOut, summary="Versions, counts and health checks")
def get_system(session: Db, _: Admin, settings: Settings = Depends(get_settings_dep)) -> SystemOut:
    return SystemOut(**SystemService(session, settings).information())


@router.get("/system/dummy", response_model=DummyDataOut, summary="Seeded placeholder records")
def get_dummy(session: Db, _: Admin) -> DummyDataOut:
    return DummyDataOut(**SystemService(session).dummy_data())


@router.post(
    "/system/dummy/remove", response_model=DummyRemovedOut, summary="Remove unused dummy records"
)
def remove_dummy(session: Db, officer: Admin) -> DummyRemovedOut:
    return DummyRemovedOut(**SystemService(session).remove_unused_dummy(officer))


# ------------------------------------------------------------- map and QR tests


@router.post("/qr/test-url", response_model=TestResultOut, summary="Check the public base URL")
def qr_test_url(_: Admin, body: TestUrlIn) -> TestResultOut:
    return TestResultOut(**check_public_url(body.url))


@router.post("/map/test-tiles", response_model=TestResultOut, summary="Fetch one map tile")
def map_test_tiles(_: Admin, body: TestTilesIn) -> TestResultOut:
    return TestResultOut(**check_tiles(body.provider, body.custom_url))


# ----------------------------------------------------------------- preferences


@router.get(
    "/me/preferences",
    response_model=PreferencesOut,
    summary="The acting officer's own display choices",
)
def get_preferences(session: Db, officer: Officer) -> PreferencesOut:
    permissions.require(officer, "settings.preferences")
    return PreferencesOut(**PreferenceService(session).get(officer))


@router.put("/me/preferences", response_model=PreferencesOut, summary="Change own display choices")
def put_preferences(session: Db, officer: Officer, body: PreferencesIn) -> PreferencesOut:
    permissions.require(officer, "settings.preferences")
    data = body.model_dump(exclude_unset=True)
    return PreferencesOut(**PreferenceService(session).update(officer, data))


__all__ = ["router"]
