"""Flag definitions and per-environment configs."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, created_at_col, uuid_pk


class Flag(Base):
    """Flag definition — shared across all environments in the project."""

    __tablename__ = "flags"

    id: Mapped[uuid.UUID] = uuid_pk()
    project_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE")
    )
    key: Mapped[str] = mapped_column(Text)
    name: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(Text)  # boolean | multivariate
    # ordered; rules/fallthrough/targets reference these by index
    variations: Mapped[list] = mapped_column(JSONB)
    temporary: Mapped[bool] = mapped_column(Boolean, default=True)
    tags: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    owner: Mapped[str | None] = mapped_column(Text)
    client_side_available: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = created_at_col()
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class FlagEnvironmentConfig(Base):
    """Per-environment targeting for one flag. One row per (flag, environment)."""

    __tablename__ = "flag_environment_configs"

    flag_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("flags.id", ondelete="CASCADE"), primary_key=True
    )
    environment_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("environments.id", ondelete="CASCADE"),
        primary_key=True,
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    targets: Mapped[list] = mapped_column(JSONB, default=list)
    rules: Mapped[list] = mapped_column(JSONB, default=list)
    fallthrough: Mapped[dict] = mapped_column(JSONB, default=lambda: {"variation": 0})
    off_variation: Mapped[int] = mapped_column(Integer, default=0)
    prerequisites: Mapped[list] = mapped_column(JSONB, default=list)
    version: Mapped[int] = mapped_column(BigInteger, default=1)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    updated_by: Mapped[str | None] = mapped_column(Text)
