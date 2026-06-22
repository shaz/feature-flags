"""Test fixtures. These run against a real Postgres (the app uses JSONB/ARRAY),
so set DATABASE_URL to a throwaway database. Tests skip if it's unreachable.
"""
from __future__ import annotations

import os
from pathlib import Path

# Default to the local docker-compose Postgres before app.config is imported.
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://fubo_flags:localdev@localhost:5432/fubo_flags",
)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402

from app.config import load_config  # noqa: E402
from app.main import create_app  # noqa: E402

_MIGRATIONS = Path(__file__).resolve().parents[2] / "migrations"
_TABLES = [
    "audit_logs", "segment_environment_configs", "segments",
    "flag_environment_configs", "flags", "sdk_credentials",
    "environments", "projects",
]


@pytest.fixture(scope="session")
def engine():
    cfg = load_config()
    eng = create_engine(cfg.database.url)
    try:
        conn = eng.connect()
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"Postgres not reachable: {exc}")
    # Clean slate, then apply schema. exec_driver_sql bypasses SQLAlchemy's
    # bind-param parsing (the JSONB defaults contain ':' which text() misreads).
    with conn.begin():
        conn.exec_driver_sql((_MIGRATIONS / "0001_init.down.sql").read_text())
        conn.exec_driver_sql((_MIGRATIONS / "0001_init.up.sql").read_text())
    conn.close()
    yield eng
    eng.dispose()


@pytest.fixture()
def client(engine):
    with engine.begin() as conn:
        conn.exec_driver_sql(f"TRUNCATE {', '.join(_TABLES)} RESTART IDENTITY CASCADE")
    with TestClient(create_app(load_config())) as c:
        yield c
