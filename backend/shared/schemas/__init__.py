"""Pydantic response schemas for shared routes."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class OrmModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class FieldOfficeOut(OrmModel):
    id: str
    code: str
    name: str
    country: str
    province: str | None
    district: str | None
    is_dummy: bool
    active: bool


class FieldOfficeRef(OrmModel):
    id: str
    code: str
    name: str


class OfficerOut(OrmModel):
    id: str
    code: str
    full_name: str
    email: str | None
    phone: str | None
    role: str
    country: str
    field_office_id: str | None
    field_office: FieldOfficeRef | None
    is_dummy: bool
    active: bool


class CurrentOfficerOut(BaseModel):
    id: str
    code: str
    full_name: str
    role: str
    country: str
    field_office_id: str | None
    field_office_name: str | None
    email: str | None = None
    phone: str | None = None
    has_photo: bool = False
    is_admin: bool
    sees_all: bool = False


class MasterOptionOut(OrmModel):
    value: str
    label: str
    sort_order: int
    country: str | None
    crop: str | None


class MasterListOut(BaseModel):
    list_key: str
    country: str | None
    crop: str | None
    items: list[MasterOptionOut]


class MasterKeysOut(BaseModel):
    keys: list[str]


class DatabaseHealth(BaseModel):
    reachable: bool
    dialect: str


class HealthOut(BaseModel):
    status: str
    app: str
    version: str
    environment: str
    database: DatabaseHealth
    server_time: datetime


class ModuleMetaOut(BaseModel):
    number: int
    name: str
    route_prefix: str
    api_prefix: str
    status: str
    build_order: int
    purpose: str


class SiteOut(OrmModel):
    id: str
    code: str
    name: str
    type: str
    crop: str
    country: str
    address: str | None
    region: str | None
    is_dummy: bool
    active: bool
