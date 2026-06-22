"""Request/response models for projects and environments."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

KEY_PATTERN = r"^[a-z0-9][a-z0-9._-]*$"


class ProjectCreate(BaseModel):
    key: str = Field(pattern=KEY_PATTERN, max_length=64)
    name: str = Field(max_length=128)
    description: str | None = None


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    key: str
    name: str
    description: str | None
    created_at: datetime


class EnvironmentCreate(BaseModel):
    key: str = Field(pattern=KEY_PATTERN, max_length=64)
    name: str = Field(max_length=128)
    sort_order: int = 0


class EnvironmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    key: str
    name: str
    sort_order: int
    created_at: datetime
