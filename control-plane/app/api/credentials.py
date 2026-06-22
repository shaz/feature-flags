"""SDK credentials, scoped to an environment."""
from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.api._common import get_environment, get_project
from app.deps import CurrentActor, DbSession
from app.models import SdkCredential
from app.schemas.credential import CredentialCreate, CredentialCreated, CredentialOut
from app.services import audit, credentials

log = logging.getLogger(__name__)
router = APIRouter(tags=["credentials"])

_BASE = "/projects/{project_key}/environments/{env_key}/credentials"


@router.post(_BASE, response_model=CredentialCreated, status_code=201)
def create_credential(
    project_key: str,
    env_key: str,
    body: CredentialCreate,
    session: DbSession,
    actor: CurrentActor,
):
    project = get_project(session, project_key)
    env = get_environment(session, project.id, env_key)

    plaintext, prefix, key_hash = credentials.generate(body.kind, env.key)
    cred = SdkCredential(
        environment_id=env.id, kind=body.kind, key_hash=key_hash, key_prefix=prefix
    )
    session.add(cred)
    session.flush()

    audit.record(
        session, actor=actor, action="credential.created",
        resource_type="credential", resource_key=prefix,
        summary=f"issued {body.kind} SDK key for {env.key}",
        project_id=project.id, environment_id=env.id,
    )
    out = CredentialOut.model_validate(cred)
    return CredentialCreated(**out.model_dump(), key=plaintext)


@router.get(_BASE, response_model=list[CredentialOut])
def list_credentials(project_key: str, env_key: str, session: DbSession):
    project = get_project(session, project_key)
    env = get_environment(session, project.id, env_key)
    return session.scalars(
        select(SdkCredential)
        .where(SdkCredential.environment_id == env.id)
        .order_by(SdkCredential.created_at.desc())
    ).all()


@router.post(_BASE + "/{cred_id}/revoke", response_model=CredentialOut)
def revoke_credential(
    project_key: str,
    env_key: str,
    cred_id: uuid.UUID,
    session: DbSession,
    actor: CurrentActor,
):
    project = get_project(session, project_key)
    env = get_environment(session, project.id, env_key)
    cred = session.get(SdkCredential, cred_id)
    if cred is None or cred.environment_id != env.id:
        raise HTTPException(404, "credential not found")
    if cred.revoked_at is not None:
        raise HTTPException(409, "credential already revoked")

    from sqlalchemy import func

    cred.revoked_at = func.now()
    audit.record(
        session, actor=actor, action="credential.revoked",
        resource_type="credential", resource_key=cred.key_prefix,
        summary=f"revoked {cred.kind} SDK key for {env.key}",
        project_id=project.id, environment_id=env.id,
    )
    session.flush()
    session.refresh(cred)
    return cred
