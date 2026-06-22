"""Shared FastAPI dependencies."""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.db import get_session

DbSession = Annotated[Session, Depends(get_session)]


def current_actor() -> str:
    """Identity of the caller for audit logging.

    STUB: returns a fixed dev user until Okta SSO + per-project roles land
    (DESIGN.md §11). Swap this dependency for real auth without touching routers.
    """
    return "dev@local"


CurrentActor = Annotated[str, Depends(current_actor)]
