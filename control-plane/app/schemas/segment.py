"""Segment request/response models. Definition is project-level; membership and
rules are per-environment (DESIGN.md §3).
"""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.catalog import KEY_PATTERN
from app.schemas.flag import Clause


class SegmentRule(BaseModel):
    clauses: list[Clause] = Field(min_length=1)


class SegmentCreate(BaseModel):
    key: str = Field(pattern=KEY_PATTERN, max_length=64)
    name: str = Field(max_length=128)
    description: str | None = None


class SegmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    key: str
    name: str
    description: str | None
    created_at: datetime


class SegmentConfigUpdate(BaseModel):
    context_kind: str = Field("user", alias="contextKind")
    included: list[str] = Field(default_factory=list)
    excluded: list[str] = Field(default_factory=list)
    rules: list[SegmentRule] = Field(default_factory=list)
    model_config = ConfigDict(populate_by_name=True)


class SegmentConfigOut(BaseModel):
    environment_key: str
    context_kind: str
    included: list[str]
    excluded: list[str]
    rules: list[SegmentRule]
    version: int
    updated_at: datetime
