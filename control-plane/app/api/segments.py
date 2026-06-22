"""Segments and per-environment membership/rules."""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api._common import get_environment, get_project, get_segment
from app.deps import CurrentActor, DbSession
from app.models import Segment, SegmentEnvironmentConfig
from app.schemas.segment import (
    SegmentConfigOut,
    SegmentConfigUpdate,
    SegmentCreate,
    SegmentOut,
)
from app.services import audit, notify

log = logging.getLogger(__name__)
router = APIRouter(tags=["segments"])


@router.post("/projects/{project_key}/segments", response_model=SegmentOut, status_code=201)
def create_segment(
    project_key: str, body: SegmentCreate, session: DbSession, actor: CurrentActor
):
    project = get_project(session, project_key)
    seg = Segment(
        project_id=project.id, key=body.key, name=body.name, description=body.description
    )
    session.add(seg)
    try:
        session.flush()
    except IntegrityError:
        raise HTTPException(409, f"segment {body.key!r} already exists")
    audit.record(
        session, actor=actor, action="segment.created", resource_type="segment",
        resource_key=seg.key, summary=f"created segment {seg.key}", project_id=project.id,
    )
    return seg


@router.get("/projects/{project_key}/segments", response_model=list[SegmentOut])
def list_segments(project_key: str, session: DbSession):
    project = get_project(session, project_key)
    return session.scalars(
        select(Segment).where(Segment.project_id == project.id).order_by(Segment.key)
    ).all()


@router.get(
    "/projects/{project_key}/segments/{segment_key}/environments/{env_key}",
    response_model=SegmentConfigOut,
)
def get_segment_config(
    project_key: str, segment_key: str, env_key: str, session: DbSession
):
    project = get_project(session, project_key)
    seg = get_segment(session, project.id, segment_key)
    env = get_environment(session, project.id, env_key)
    cfg = session.get(SegmentEnvironmentConfig, (seg.id, env.id))
    if cfg is None:
        raise HTTPException(404, "segment has no config in this environment")
    return _config_out(env.key, cfg)


@router.put(
    "/projects/{project_key}/segments/{segment_key}/environments/{env_key}",
    response_model=SegmentConfigOut,
)
def update_segment_config(
    project_key: str,
    segment_key: str,
    env_key: str,
    body: SegmentConfigUpdate,
    session: DbSession,
    actor: CurrentActor,
):
    project = get_project(session, project_key)
    seg = get_segment(session, project.id, segment_key)
    env = get_environment(session, project.id, env_key)

    cfg = session.get(SegmentEnvironmentConfig, (seg.id, env.id))
    if cfg is None:  # upsert — segments aren't auto-seeded per env
        cfg = SegmentEnvironmentConfig(segment_id=seg.id, environment_id=env.id, version=0)
        session.add(cfg)

    cfg.context_kind = body.context_kind
    cfg.included = body.included
    cfg.excluded = body.excluded
    cfg.rules = [r.model_dump(by_alias=True) for r in body.rules]
    cfg.version += 1

    audit.record(
        session, actor=actor, action="segment.updated", resource_type="segment",
        resource_key=seg.key,
        summary=f"updated segment {seg.key} in {env.key} "
                f"({len(cfg.included)} included, {len(cfg.rules)} rules)",
        project_id=project.id, environment_id=env.id,
    )
    session.flush()
    notify.env_changed(session, env.id)
    return _config_out(env.key, cfg)


def _config_out(env_key: str, cfg: SegmentEnvironmentConfig) -> SegmentConfigOut:
    return SegmentConfigOut(
        environment_key=env_key,
        context_kind=cfg.context_kind,
        included=cfg.included,
        excluded=cfg.excluded,
        rules=cfg.rules,
        version=cfg.version,
        updated_at=cfg.updated_at,
    )
