"""Device request/response models."""

from __future__ import annotations

from pydantic import BaseModel


class EnrollTokenRequest(BaseModel):
    name: str = "new-device"
    ttl: str = "1h"
    kind: str = "enrollment"


class CiTokenRequest(BaseModel):
    app: str
    env: str
    ttl: str = "30d"
