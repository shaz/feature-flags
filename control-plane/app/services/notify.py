"""Change-notification bus.

When a flag/segment config changes, the data plane reloads that environment's
ruleset (DESIGN.md §2, §6). The `postgres` backend issues `pg_notify` in the
same transaction as the change, so the signal fires exactly when the change
commits (and rolls back with it if the transaction aborts). `log` is a no-op
used in environments without a data plane.
"""
from __future__ import annotations

import logging
import uuid

from sqlalchemy import text
from sqlalchemy.orm import Session

log = logging.getLogger(__name__)

_backend = "log"
CHANNEL = "flags_changed"


def configure(backend: str) -> None:
    global _backend
    _backend = backend
    log.debug("notify backend = %s", backend)


def env_changed(session: Session, environment_id: uuid.UUID) -> None:
    """Signal that an environment's ruleset changed."""
    if _backend == "postgres":
        session.execute(
            text("SELECT pg_notify(:chan, :payload)"),
            {"chan": CHANNEL, "payload": str(environment_id)},
        )
        log.debug("pg_notify %s %s", CHANNEL, environment_id)
    elif _backend == "log":
        log.info("[notify:stub] environment %s changed", environment_id)
    else:
        raise NotImplementedError(f"notify backend {_backend!r} not implemented")
