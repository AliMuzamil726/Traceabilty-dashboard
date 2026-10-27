"""Request and response schemas for Module 8 (Settings).

Values are deliberately loose where the registry is the authority: a setting's value is
``Any``, because what is valid depends on its definition, and the service validates it
against that definition rather than against a schema written twice.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class OrmModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ------------------------------------------------------------------ generic values


class DefinitionOut(BaseModel):
    key: str
    group: str
    label: str
    description: str
    type: str
    default: Any
    minimum: float | None = None
    maximum: float | None = None
    pattern: str | None = None
    choices: list[Any] | None = None
    sensitive: bool = False
    needs_restart: bool = False
    read_by: list[str] = Field(default_factory=list)
    public: bool = False


class SettingOut(DefinitionOut):
    value: Any
    source: str
    version: int
    is_default: bool
    #: Who last changed it and when, for the "Last changed by" line under each card.
    changed_by: str | None = None
    changed_at: str | None = None


class SettingsPageOut(BaseModel):
    items: list[SettingOut]
    groups: list[str]


class SettingIn(BaseModel):
    value: Any
    expected_version: int | None = None
    reason: str | None = Field(default=None, max_length=500)


class HistoryOut(BaseModel):
    id: str
    key: str
    old_value: Any
    new_value: Any
    changed_by: str | None
    changed_by_name: str | None = None
    changed_at: datetime
    reason: str | None


# ------------------------------------------------------------------------- people


class OfficerOut(BaseModel):
    id: str
    code: str
    full_name: str
    email: str | None
    phone: str | None
    role: str
    country: str
    field_office_id: str | None
    field_office_name: str | None = None
    is_dummy: bool
    active: bool
    usage: int = 0
    last_activity: datetime | None = None
    #: False when this is the last active administrator, who cannot be removed.
    can_deactivate: bool = True


class OfficerIn(BaseModel):
    code: str | None = Field(default=None, max_length=32)
    full_name: str = Field(max_length=120)
    email: str | None = Field(default=None, max_length=254)
    phone: str | None = Field(default=None, max_length=32)
    role: str = "officer"
    country: str = Field(default="PK", max_length=2)
    field_office_id: str | None = None
    active: bool = True


class OfficerUpdateIn(BaseModel):
    full_name: str | None = Field(default=None, max_length=120)
    email: str | None = Field(default=None, max_length=254)
    phone: str | None = Field(default=None, max_length=32)
    role: str | None = None
    field_office_id: str | None = None
    active: bool | None = None


class OfficeOut(BaseModel):
    id: str
    code: str
    name: str
    country: str
    province: str | None
    district: str | None
    is_dummy: bool
    active: bool
    officer_count: int = 0
    usage: int = 0


class OfficeIn(BaseModel):
    code: str | None = Field(default=None, max_length=32)
    name: str = Field(max_length=120)
    country: str = Field(default="PK", max_length=2)
    province: str | None = Field(default=None, max_length=120)
    district: str | None = Field(default=None, max_length=120)
    active: bool = True


class OfficeUpdateIn(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    province: str | None = Field(default=None, max_length=120)
    district: str | None = Field(default=None, max_length=120)
    active: bool | None = None


class UsageItemOut(BaseModel):
    label: str
    count: int


class SiteOut(BaseModel):
    id: str
    code: str
    name: str
    type: str
    crop: str
    country: str
    address: str | None
    region: str | None
    contact_person: str | None
    contact_phone: str | None
    is_dummy: bool
    active: bool
    usage: int = 0
    usage_breakdown: list[UsageItemOut] = Field(default_factory=list)
    code_locked: bool = False


class SiteIn(BaseModel):
    code: str = Field(max_length=32)
    name: str = Field(max_length=120)
    type: str
    crop: str
    country: str = Field(default="PK", max_length=2)
    address: str | None = Field(default=None, max_length=255)
    region: str | None = Field(default=None, max_length=120)
    contact_person: str | None = Field(default=None, max_length=120)
    contact_phone: str | None = Field(default=None, max_length=32)
    active: bool = True


class SiteUpdateIn(BaseModel):
    code: str | None = Field(default=None, max_length=32)
    name: str | None = Field(default=None, max_length=120)
    address: str | None = Field(default=None, max_length=255)
    region: str | None = Field(default=None, max_length=120)
    contact_person: str | None = Field(default=None, max_length=120)
    contact_phone: str | None = Field(default=None, max_length=32)
    active: bool | None = None


# -------------------------------------------------------------------------- lists


class ListSummaryOut(BaseModel):
    key: str
    label: str
    group: str
    values: int
    active_values: int
    required_by: list[str] = Field(default_factory=list)


class ListValueOut(BaseModel):
    id: str
    list_key: str
    value: str
    label: str
    sort_order: int
    active: bool
    crop: str | None = None
    country: str | None = None
    usage: int = 0
    can_delete: bool = True


class ListValueIn(BaseModel):
    value: str | None = Field(default=None, max_length=64)
    label: str = Field(max_length=160)
    crop: str | None = None
    country: str | None = Field(default=None, max_length=2)
    sort_order: int | None = None
    active: bool = True


class ListValueUpdateIn(BaseModel):
    label: str | None = Field(default=None, max_length=160)
    active: bool | None = None


class ReorderIn(BaseModel):
    ids: list[str]


class ImportReportOut(BaseModel):
    """What an import did, or would do with ``dry_run=true``."""

    created: int
    updated: int
    skipped: int
    errors: list[dict[str, Any]] = Field(default_factory=list)
    ok: bool = True


# ---------------------------------------------------------------------- locations


class LocationNodeOut(BaseModel):
    id: str
    code: str | None = None
    name: str
    level: str
    country: str
    active: bool
    usage: int = 0
    children: list[LocationNodeOut] = Field(default_factory=list)


class LocationTreeOut(BaseModel):
    country: str
    labels: dict[str, str]
    levels: list[str]
    items: list[LocationNodeOut]


class LocationOut(BaseModel):
    id: str
    code: str | None = None
    name: str
    level: str


class LocationIn(BaseModel):
    name: str = Field(max_length=120)
    level: str
    parent_id: str | None = None
    country: str = Field(default="PK", max_length=2)
    active: bool = True


class LocationUpdateIn(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    active: bool | None = None


class MergeIn(BaseModel):
    source_id: str
    target_id: str


class RenamePreviewOut(BaseModel):
    id: str
    name: str
    level: str
    affected_farmers: int


# ------------------------------------------------------------------- owned config


class ConfigIn(BaseModel):
    values: dict[str, Any]
    expected_version: int | None = None


class ClockPreviewIn(BaseModel):
    values: dict[str, Any]


# ------------------------------------------------------------------- permissions


class PermissionRowOut(BaseModel):
    key: str
    module: int | None
    label: str
    description: str
    officer: bool
    staff: bool
    admin: bool


# -------------------------------------------------------------------- audit log


class AuditEntryOut(BaseModel):
    id: str
    entity: str
    entity_id: str
    module: int | None
    action: str
    officer_id: str | None
    officer_name: str | None
    diff: dict[str, Any]
    request_id: str | None
    created_at: datetime


class AuditPageOut(BaseModel):
    items: list[AuditEntryOut]
    total: int
    page: int
    page_size: int


class AuditFacetsOut(BaseModel):
    entities: list[str]
    actions: list[str]
    officers: list[dict[str, str]]
    modules: list[int]


# ----------------------------------------------------------------------- backups


class BackupOut(BaseModel):
    id: str
    filename: str
    size_bytes: int
    created_by: str | None
    created_at: datetime
    note: str | None
    kind: str
    present: bool = True


class BackupStatusOut(BaseModel):
    supported: bool
    dialect: str
    reason: str | None = None
    instructions: str | None = None
    directory: str | None = None
    database_bytes: int | None = None
    maintenance: bool = False


class BackupIn(BaseModel):
    note: str | None = Field(default=None, max_length=500)


class RestoreIn(BaseModel):
    confirm: str


class RestoreOut(BaseModel):
    filename: str
    safety_backup: str
    integrity: str
    counts_before: dict[str, int]
    counts_after: dict[str, int]


# ------------------------------------------------------------------------ system


class HealthCheckOut(BaseModel):
    key: str
    label: str
    status: str
    detail: str


class SystemOut(BaseModel):
    app: dict[str, Any]
    runtime: dict[str, Any]
    database: dict[str, Any]
    counts: list[dict[str, Any]]
    health: list[HealthCheckOut]
    seed: dict[str, Any]


class DummyRowOut(BaseModel):
    id: str
    code: str
    name: str
    usage: int


class DummyDataOut(BaseModel):
    officers: list[DummyRowOut]
    offices: list[DummyRowOut]
    sites: list[DummyRowOut]
    removable: int


class DummyRemovedOut(BaseModel):
    removed: dict[str, list[str]]
    removed_total: int
    kept: list[dict[str, Any]]


# ------------------------------------------------------------------ public config


class PublicConfigOut(BaseModel):
    settings: dict[str, Any]
    map: dict[str, Any]
    qr: dict[str, Any]
    programme: dict[str, Any]
    cache_seconds: int


class TestUrlIn(BaseModel):
    url: str = Field(max_length=500)


class TestTilesIn(BaseModel):
    provider: str | None = None
    custom_url: str | None = Field(default=None, max_length=500)


class TestResultOut(BaseModel):
    ok: bool
    status: int | None = None
    detail: str
    warning: str | None = None
    url: str | None = None


# ------------------------------------------------------------------- preferences


class PreferencesOut(BaseModel):
    sidebar_collapsed: bool
    table_density: str
    default_crop: str


class PreferencesIn(BaseModel):
    sidebar_collapsed: bool | None = None
    table_density: str | None = None
    default_crop: str | None = None


LocationNodeOut.model_rebuild()
