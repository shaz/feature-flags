"""Load configuration from config.yaml with environment-variable overrides.

Precedence: env var > config.yaml > built-in default. Secrets only ever come
from the environment.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import yaml

_DEFAULT_PATH = Path(__file__).resolve().parent.parent / "config" / "config.yaml"


@dataclass(frozen=True)
class ServerConfig:
    host: str
    port: int


@dataclass(frozen=True)
class DatabaseConfig:
    url: str
    pool_size: int


@dataclass(frozen=True)
class LoggingConfig:
    level: str
    format: str


@dataclass(frozen=True)
class Config:
    server: ServerConfig
    database: DatabaseConfig
    logging: LoggingConfig
    notify_backend: str


def _build_database_url(db: dict) -> str:
    """Prefer DATABASE_URL; otherwise assemble from parts + DATABASE_PASSWORD."""
    if url := os.getenv("DATABASE_URL"):
        return url
    password = os.getenv("DATABASE_PASSWORD", "")
    auth = f"{db['user']}:{password}" if password else db["user"]
    return f"postgresql+psycopg://{auth}@{db['host']}:{db['port']}/{db['name']}"


def load_config(path: Path | None = None) -> Config:
    raw = yaml.safe_load((path or _DEFAULT_PATH).read_text())

    srv, db, log = raw["server"], raw["database"], raw["logging"]
    return Config(
        server=ServerConfig(
            host=os.getenv("FUBO_FLAGS_HOST", srv["host"]),
            port=int(os.getenv("FUBO_FLAGS_PORT", srv["port"])),
        ),
        database=DatabaseConfig(
            url=_build_database_url(db),
            pool_size=int(os.getenv("FUBO_FLAGS_DB_POOL", db["pool_size"])),
        ),
        logging=LoggingConfig(
            level=os.getenv("FUBO_FLAGS_LOG_LEVEL", log["level"]),
            format=log["format"],
        ),
        notify_backend=os.getenv("FUBO_FLAGS_NOTIFY", raw["notify"]["backend"]),
    )
