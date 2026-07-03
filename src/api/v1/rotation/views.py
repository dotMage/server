"""Pydantic models for AK rotation endpoints (spec L)."""

from __future__ import annotations

from pydantic import BaseModel


class RotateBeginRequest(BaseModel):
    new_key_gen: int
    nonce_ak: str
    wrapped_ak: str
    salt_rc: str | None = None
    nonce_rc: str | None = None
    wrapped_ak_rc: str | None = None


class PutBlobRequest(BaseModel):
    blob: str
    key_gen: int
