"""Process-wide logging configuration."""
from __future__ import annotations

import logging

from app.config import LoggingConfig


def configure_logging(cfg: LoggingConfig) -> None:
    logging.basicConfig(level=cfg.level, format=cfg.format)
    # SQLAlchemy echo is noisy; keep it at WARNING unless we're at DEBUG.
    if cfg.level != "DEBUG":
        logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
