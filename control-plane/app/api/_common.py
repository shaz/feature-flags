"""Shared lookup helpers that raise 404 when a resource is missing."""
from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Environment, Flag, Project, Segment


def get_project(session: Session, project_key: str) -> Project:
    project = session.scalar(select(Project).where(Project.key == project_key))
    if project is None:
        raise HTTPException(404, f"project {project_key!r} not found")
    return project


def get_environment(session: Session, project_id, env_key: str) -> Environment:
    env = session.scalar(
        select(Environment).where(
            Environment.project_id == project_id, Environment.key == env_key
        )
    )
    if env is None:
        raise HTTPException(404, f"environment {env_key!r} not found")
    return env


def get_flag(session: Session, project_id, flag_key: str) -> Flag:
    flag = session.scalar(
        select(Flag).where(Flag.project_id == project_id, Flag.key == flag_key)
    )
    if flag is None:
        raise HTTPException(404, f"flag {flag_key!r} not found")
    return flag


def get_segment(session: Session, project_id, segment_key: str) -> Segment:
    seg = session.scalar(
        select(Segment).where(
            Segment.project_id == project_id, Segment.key == segment_key
        )
    )
    if seg is None:
        raise HTTPException(404, f"segment {segment_key!r} not found")
    return seg
