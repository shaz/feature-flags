"""Change-notification bus.

When a flag/segment config changes, the data plane needs to reload that
environment's ruleset (DESIGN.md §2, §6). Phase 1 only logs intent; the
`postgres` (LISTEN/NOTIFY) and `redis` backends land with the data plane.
"""
from __future__ import annotations

import logging
import uuid

log = logging.getLogger(__name__)

_backend = "log"


def configure(backend: str) -> None:
    global _backend
    _backend = backend
    log.debug("notify backend = %s", backend)


def env_changed(environment_id: uuid.UUID) -> None:
    """Signal that an environment's ruleset changed."""
    if _backend == "log":
        log.info("[notify:stub] environment %s changed", environment_id)
        return
    # TODO(phase-2): postgres NOTIFY flags_changed / redis publish
    raise NotImplementedError(f"notify backend {_backend!r} not implemented yet")
