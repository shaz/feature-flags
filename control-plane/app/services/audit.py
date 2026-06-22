"""Audit-log writer. Always called inside the same transaction as the change it
records, so an audit row and its change commit or roll back together.
"""
from __future__ import annotations

import logging
import uuid

from sqlalchemy.orm import Session

from app.models import AuditLog

log = logging.getLogger(__name__)


def record(
    session: Session,
    *,
    actor: str,
    action: str,
    resource_type: str,
    resource_key: str,
    summary: str,
    project_id: uuid.UUID,
    environment_id: uuid.UUID | None = None,
    diff: dict | None = None,
) -> None:
    log.debug("audit %s %s %s by %s", action, resource_type, resource_key, actor)
    session.add(
        AuditLog(
            actor=actor,
            action=action,
            resource_type=resource_type,
            resource_key=resource_key,
            summary=summary,
            project_id=project_id,
            environment_id=environment_id,
            diff=diff,
        )
    )
