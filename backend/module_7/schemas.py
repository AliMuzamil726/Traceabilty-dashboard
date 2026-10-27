"""Request schemas for Module 7 (QR Tracing). Responses are plain JSON documented in CONTRACTS."""

from __future__ import annotations

from pydantic import BaseModel, Field


class SerialsIn(BaseModel):
    serials: list[str] = Field(min_length=1, max_length=480)


class ReasonIn(BaseModel):
    reason: str = Field(default="", max_length=500)
