"""Database engine and session management."""
from __future__ import annotations

import logging
from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import DatabaseConfig

log = logging.getLogger(__name__)

_SessionFactory: sessionmaker[Session] | None = None


def init_engine(cfg: DatabaseConfig) -> None:
    global _SessionFactory
    log.debug("creating database engine pool_size=%s", cfg.pool_size)
    engine = create_engine(cfg.url, pool_size=cfg.pool_size, pool_pre_ping=True)
    _SessionFactory = sessionmaker(bind=engine, expire_on_commit=False)


def get_session() -> Iterator[Session]:
    """FastAPI dependency: one transaction per request, commit on success."""
    if _SessionFactory is None:
        raise RuntimeError("database engine not initialized")
    session = _SessionFactory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
