"""Flags and per-environment targeting."""
from __future__ import annotations

import logging
import secrets

from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api._common import get_environment, get_flag, get_project
from app.deps import CurrentActor, DbSession
from app.models import Environment, Flag, FlagEnvironmentConfig
from app.schemas.flag import FlagConfigOut, FlagConfigUpdate, FlagCreate, FlagOut
from app.services import audit, notify

log = logging.getLogger(__name__)
router = APIRouter(tags=["flags"])


def _validate_indices(cfg: FlagConfigUpdate, variation_count: int) -> None:
    """Every variation reference must point at an existing variation index."""
    bad: list[str] = []

    def check(idx: int, where: str) -> None:
        if not 0 <= idx < variation_count:
            bad.append(f"{where} -> variation {idx}")

    check(cfg.off_variation, "offVariation")
    for t in cfg.targets:
        check(t.variation, f"target[{t.context_kind}]")
    for i, rule in enumerate(cfg.rules):
        if rule.variation is not None:
            check(rule.variation, f"rule[{i}]")
        if rule.rollout is not None:
            for wv in rule.rollout.variations:
                check(wv.variation, f"rule[{i}].rollout")
    if cfg.fallthrough.variation is not None:
        check(cfg.fallthrough.variation, "fallthrough")
    if cfg.fallthrough.rollout is not None:
        for wv in cfg.fallthrough.rollout.variations:
            check(wv.variation, "fallthrough.rollout")

    if bad:
        raise HTTPException(422, f"variation index out of range: {', '.join(bad)}")


@router.post("/projects/{project_key}/flags", response_model=FlagOut, status_code=201)
def create_flag(
    project_key: str, body: FlagCreate, session: DbSession, actor: CurrentActor
):
    project = get_project(session, project_key)
    flag = Flag(
        project_id=project.id,
        key=body.key,
        name=body.name,
        description=body.description,
        kind=body.kind,
        variations=[v.model_dump() for v in body.variations],
        salt=secrets.token_hex(8),
        temporary=body.temporary,
        tags=body.tags,
        owner=body.owner,
        client_side_available=body.client_side_available,
    )
    session.add(flag)
    try:
        session.flush()
    except IntegrityError:
        raise HTTPException(409, f"flag {body.key!r} already exists")

    # Create a default (off) config for every environment in the project.
    envs = session.scalars(
        select(Environment).where(Environment.project_id == project.id)
    ).all()
    for env in envs:
        session.add(
            FlagEnvironmentConfig(
                flag_id=flag.id, environment_id=env.id, updated_by=actor
            )
        )

    audit.record(
        session, actor=actor, action="flag.created", resource_type="flag",
        resource_key=flag.key, summary=f"created flag {flag.key}",
        project_id=project.id,
    )
    return flag


@router.get("/projects/{project_key}/flags", response_model=list[FlagOut])
def list_flags(project_key: str, session: DbSession):
    project = get_project(session, project_key)
    return session.scalars(
        select(Flag)
        .where(Flag.project_id == project.id, Flag.archived_at.is_(None))
        .order_by(Flag.key)
    ).all()


@router.get("/projects/{project_key}/flags/{flag_key}", response_model=FlagOut)
def get_one_flag(project_key: str, flag_key: str, session: DbSession):
    project = get_project(session, project_key)
    return get_flag(session, project.id, flag_key)


@router.get(
    "/projects/{project_key}/flags/{flag_key}/environments/{env_key}",
    response_model=FlagConfigOut,
)
def get_flag_config(
    project_key: str, flag_key: str, env_key: str, session: DbSession
):
    project = get_project(session, project_key)
    flag = get_flag(session, project.id, flag_key)
    env = get_environment(session, project.id, env_key)
    cfg = session.get(FlagEnvironmentConfig, (flag.id, env.id))
    if cfg is None:
        raise HTTPException(404, "flag has no config in this environment")
    return _config_out(env.key, cfg)


@router.put(
    "/projects/{project_key}/flags/{flag_key}/environments/{env_key}",
    response_model=FlagConfigOut,
)
def update_flag_config(
    project_key: str,
    flag_key: str,
    env_key: str,
    body: FlagConfigUpdate,
    session: DbSession,
    actor: CurrentActor,
):
    project = get_project(session, project_key)
    flag = get_flag(session, project.id, flag_key)
    env = get_environment(session, project.id, env_key)
    cfg = session.get(FlagEnvironmentConfig, (flag.id, env.id))
    if cfg is None:
        raise HTTPException(404, "flag has no config in this environment")

    _validate_indices(body, len(flag.variations))

    before = _config_snapshot(cfg)
    cfg.enabled = body.enabled
    cfg.targets = [t.model_dump(by_alias=True) for t in body.targets]
    cfg.rules = [r.model_dump(by_alias=True, exclude_none=True) for r in body.rules]
    cfg.fallthrough = body.fallthrough.model_dump(by_alias=True, exclude_none=True)
    cfg.off_variation = body.off_variation
    cfg.prerequisites = [p.model_dump(by_alias=True) for p in body.prerequisites]
    cfg.version += 1
    cfg.updated_by = actor
    after = _config_snapshot(cfg)

    audit.record(
        session, actor=actor, action="flag.targeting.updated", resource_type="flag",
        resource_key=flag.key,
        summary=f"updated targeting for {flag.key} in {env.key} "
                f"(targeting {'on' if cfg.enabled else 'off'})",
        project_id=project.id, environment_id=env.id,
        diff={"before": before, "after": after},
    )
    session.flush()
    notify.env_changed(env.id)
    return _config_out(env.key, cfg)


def _config_snapshot(cfg: FlagEnvironmentConfig) -> dict:
    return {
        "enabled": cfg.enabled,
        "targets": cfg.targets,
        "rules": cfg.rules,
        "fallthrough": cfg.fallthrough,
        "offVariation": cfg.off_variation,
        "prerequisites": cfg.prerequisites,
        "version": cfg.version,
    }


def _config_out(env_key: str, cfg: FlagEnvironmentConfig) -> FlagConfigOut:
    return FlagConfigOut(
        environment_key=env_key,
        enabled=cfg.enabled,
        targets=cfg.targets,
        rules=cfg.rules,
        fallthrough=cfg.fallthrough,
        off_variation=cfg.off_variation,
        prerequisites=cfg.prerequisites,
        version=cfg.version,
        updated_at=cfg.updated_at,
        updated_by=cfg.updated_by,
    )
