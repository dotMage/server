"""Pydantic models for team endpoints (spec K/B.9)."""

from __future__ import annotations

from pydantic import BaseModel


class InviteRequest(BaseModel):
    name: str
    role: str = "editor"
    ttl: str = "24h"
    sealed_ak: str
    nonce_inv: str
    redeem_hash: str


class RedeemRequest(BaseModel):
    invitation_id: str
    redeem_secret: str


class CompleteRequest(BaseModel):
    invitation_id: str
    redeem_secret: str
    device_name: str
    salt: str
    argon_memory: int
    argon_iterations: int
    argon_parallelism: int
    argon_version: int
    nonce_ak: str
    wrapped_ak: str
    salt_rc: str | None = None
    nonce_rc: str | None = None
    wrapped_ak_rc: str | None = None


class PatchUserRequest(BaseModel):
    role: str
