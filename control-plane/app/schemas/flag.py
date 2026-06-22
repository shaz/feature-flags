"""Request/response models for flags and per-environment targeting.

These Pydantic models are also the validation layer for the targeting JSONB
shapes specified in DESIGN.md §4 — clauses, rollouts, rules, targets.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.catalog import KEY_PATTERN

FlagKind = Literal["boolean", "multivariate"]

Operator = Literal[
    "in", "endsWith", "startsWith", "matches", "contains",
    "lessThan", "greaterThan", "before", "after",
    "semVerEqual", "semVerLess", "semVerGreater", "segmentMatch",
]


# ── Targeting building blocks ────────────────────────────────────────────────

class Variation(BaseModel):
    name: str = Field(max_length=128)
    value: Any  # boolean | string | number | json, by flag kind


class Clause(BaseModel):
    context_kind: str = Field("user", alias="contextKind")
    attribute: str
    op: Operator
    values: list[Any]
    negate: bool = False
    model_config = ConfigDict(populate_by_name=True)


class WeightedVariation(BaseModel):
    variation: int = Field(ge=0)
    weight: int = Field(ge=0, le=100_000)


class Rollout(BaseModel):
    context_kind: str = Field("user", alias="contextKind")
    bucket_by: str = Field("key", alias="bucketBy")
    variations: list[WeightedVariation]
    model_config = ConfigDict(populate_by_name=True)

    @model_validator(mode="after")
    def _weights_sum_to_100k(self) -> "Rollout":
        total = sum(v.weight for v in self.variations)
        if total != 100_000:
            raise ValueError(f"rollout weights must sum to 100000, got {total}")
        return self


class _VariationOrRollout(BaseModel):
    """Exactly one of variation / rollout must be set."""

    variation: int | None = Field(default=None, ge=0)
    rollout: Rollout | None = None

    @model_validator(mode="after")
    def _exactly_one(self) -> "_VariationOrRollout":
        if (self.variation is None) == (self.rollout is None):
            raise ValueError("set exactly one of 'variation' or 'rollout'")
        return self


class Rule(_VariationOrRollout):
    clauses: list[Clause] = Field(min_length=1)


class Fallthrough(_VariationOrRollout):
    pass


class Target(BaseModel):
    context_kind: str = Field("user", alias="contextKind")
    variation: int = Field(ge=0)
    keys: list[str]
    model_config = ConfigDict(populate_by_name=True)


class Prerequisite(BaseModel):
    flag_key: str = Field(alias="flagKey")
    variation: int = Field(ge=0)
    model_config = ConfigDict(populate_by_name=True)


# ── Flag definition ──────────────────────────────────────────────────────────

class FlagCreate(BaseModel):
    key: str = Field(pattern=KEY_PATTERN, max_length=64)
    name: str = Field(max_length=128)
    description: str | None = None
    kind: FlagKind
    variations: list[Variation] = Field(min_length=2)
    temporary: bool = True
    tags: list[str] = Field(default_factory=list)
    owner: str | None = None
    client_side_available: bool = Field(False, alias="clientSideAvailable")
    model_config = ConfigDict(populate_by_name=True)

    @model_validator(mode="after")
    def _boolean_has_two(self) -> "FlagCreate":
        if self.kind == "boolean" and len(self.variations) != 2:
            raise ValueError("boolean flags must have exactly 2 variations")
        return self


class FlagOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    key: str
    name: str
    description: str | None
    kind: str
    variations: list[Variation]
    salt: str
    temporary: bool
    tags: list[str]
    owner: str | None
    client_side_available: bool
    created_at: datetime
    archived_at: datetime | None


# ── Per-environment config ───────────────────────────────────────────────────

class FlagConfigUpdate(BaseModel):
    """Full replace of an environment's targeting for a flag."""

    enabled: bool
    targets: list[Target] = Field(default_factory=list)
    rules: list[Rule] = Field(default_factory=list)
    fallthrough: Fallthrough
    off_variation: int = Field(0, ge=0, alias="offVariation")
    prerequisites: list[Prerequisite] = Field(default_factory=list)
    model_config = ConfigDict(populate_by_name=True)


class FlagConfigOut(BaseModel):
    environment_key: str
    enabled: bool
    targets: list[Target]
    rules: list[Rule]
    fallthrough: Fallthrough
    off_variation: int
    prerequisites: list[Prerequisite]
    version: int
    updated_at: datetime
    updated_by: str | None
