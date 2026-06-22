"""Projects and environments."""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api._common import get_project
from app.deps import CurrentActor, DbSession
from app.models import Environment, Project
from app.schemas.catalog import (
    EnvironmentCreate,
    EnvironmentOut,
    ProjectCreate,
    ProjectOut,
)
from app.services import audit

log = logging.getLogger(__name__)
router = APIRouter(tags=["projects"])


@router.post("/projects", response_model=ProjectOut, status_code=201)
def create_project(body: ProjectCreate, session: DbSession, actor: CurrentActor):
    project = Project(key=body.key, name=body.name, description=body.description)
    session.add(project)
    try:
        session.flush()
    except IntegrityError:
        raise HTTPException(409, f"project {body.key!r} already exists")
    audit.record(
        session, actor=actor, action="project.created", resource_type="project",
        resource_key=project.key, summary=f"created project {project.key}",
        project_id=project.id,
    )
    return project


@router.get("/projects", response_model=list[ProjectOut])
def list_projects(session: DbSession):
    return session.scalars(select(Project).order_by(Project.key)).all()


@router.get("/projects/{project_key}", response_model=ProjectOut)
def get_one_project(project_key: str, session: DbSession):
    return get_project(session, project_key)


@router.post(
    "/projects/{project_key}/environments",
    response_model=EnvironmentOut,
    status_code=201,
)
def create_environment(
    project_key: str, body: EnvironmentCreate, session: DbSession, actor: CurrentActor
):
    project = get_project(session, project_key)
    env = Environment(
        project_id=project.id, key=body.key, name=body.name, sort_order=body.sort_order
    )
    session.add(env)
    try:
        session.flush()
    except IntegrityError:
        raise HTTPException(409, f"environment {body.key!r} already exists")
    audit.record(
        session, actor=actor, action="environment.created",
        resource_type="environment", resource_key=env.key,
        summary=f"created environment {env.key}", project_id=project.id,
        environment_id=env.id,
    )
    return env


@router.get(
    "/projects/{project_key}/environments", response_model=list[EnvironmentOut]
)
def list_environments(project_key: str, session: DbSession):
    project = get_project(session, project_key)
    return session.scalars(
        select(Environment)
        .where(Environment.project_id == project.id)
        .order_by(Environment.sort_order, Environment.key)
    ).all()
