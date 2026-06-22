"""FastAPI application factory for the fubo-flags control plane."""
from __future__ import annotations

import logging

from fastapi import FastAPI

from app.api import flags, projects
from app.config import Config, load_config
from app.db import init_engine
from app.logging_setup import configure_logging
from app.services import notify

log = logging.getLogger(__name__)


def create_app(config: Config | None = None) -> FastAPI:
    cfg = config or load_config()
    configure_logging(cfg.logging)
    log.info("starting fubo-flags control plane")

    init_engine(cfg.database)
    notify.configure(cfg.notify_backend)

    app = FastAPI(title="fubo-flags control plane", version="0.1.0")
    app.include_router(projects.router, prefix="/api/v1")
    app.include_router(flags.router, prefix="/api/v1")

    @app.get("/healthz", tags=["meta"])
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
