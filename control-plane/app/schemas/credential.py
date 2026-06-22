"""SDK credential request/response models."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

CredentialKind = Literal["server", "client", "mobile"]


class CredentialCreate(BaseModel):
    kind: CredentialKind


class CredentialOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    kind: str
    key_prefix: str
    created_at: datetime
    revoked_at: datetime | None


class CredentialCreated(CredentialOut):
    # The full plaintext key — returned ONCE, on creation. Only the hash is stored.
    key: str
