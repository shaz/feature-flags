"""Read access to the audit log."""
from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select

from app.api._common import get_project
from app.deps import DbSession
from app.models import AuditLog

router = APIRouter(tags=["audit"])


class AuditEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    actor: str
    action: str
    resource_type: str
    resource_key: str
    summary: str
    environment_id: uuid.UUID | None
    created_at: datetime


@router.get("/projects/{project_key}/audit", response_model=list[AuditEntry])
def list_audit(
    project_key: str,
    session: DbSession,
    limit: int = Query(50, ge=1, le=500),
):
    project = get_project(session, project_key)
    return session.scalars(
        select(AuditLog)
        .where(AuditLog.project_id == project.id)
        .order_by(AuditLog.id.desc())
        .limit(limit)
    ).all()
