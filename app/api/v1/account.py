"""Account endpoints: init, get keys, update keys."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import (
    generate_device_token,
    generate_refresh_token,
    optional_token,
    require_device_token,
)
from app.core.config import settings
from app.core.ratelimit import check_rate_limit
from app.db.models import Account, AuditLog, Device
from app.db.session import get_db

router = APIRouter(prefix="/account", tags=["account"])


class InitBody(BaseModel):
    bootstrap_secret: str
    salt: str
    argon_memory: int = 65536
    argon_iterations: int = 3
    argon_parallelism: int = 1
    argon_version: int = 19
    nonce_ak: str
    wrapped_ak: str
    salt_rc: str | None = None
    nonce_rc: str | None = None
    wrapped_ak_rc: str | None = None
    device_name: str = "cli"


class PatchKeysBody(BaseModel):
    nonce_ak: str
    wrapped_ak: str
    salt: str | None = None


@router.post("/init")
def account_init(
    body: InitBody,
    request: Request,
    db: Session = Depends(get_db),
    _rl: None = Depends(check_rate_limit),
) -> JSONResponse:
    # Check if account already exists
    existing = db.execute(select(Account)).scalar_one_or_none()
    if existing is not None:
        return JSONResponse(
            status_code=409,
            content={"error": {"code": "account_exists", "message": "Account already initialized"}},
        )

    # Verify bootstrap secret
    if body.bootstrap_secret != settings.bootstrap_secret:
        return JSONResponse(
            status_code=403,
            content={"error": {"code": "invalid_bootstrap", "message": "Invalid bootstrap secret"}},
        )

    now = datetime.now(timezone.utc)

    account = Account(
        salt=body.salt,
        argon_memory=body.argon_memory,
        argon_iterations=body.argon_iterations,
        argon_parallelism=body.argon_parallelism,
        argon_version=body.argon_version,
        nonce_ak=body.nonce_ak,
        wrapped_ak=body.wrapped_ak,
        salt_rc=body.salt_rc,
        nonce_rc=body.nonce_rc,
        wrapped_ak_rc=body.wrapped_ak_rc,
        bootstrap_secret_hash=settings.bootstrap_secret_hash,
        bootstrap_used=True,
        created_at=now,
    )
    db.add(account)
    db.flush()

    # Create first device
    raw_token, token_hash = generate_device_token()
    raw_refresh, refresh_hash = generate_refresh_token()

    device = Device(
        account_id=account.id,
        name=body.device_name,
        token_hash=token_hash,
        refresh_hash=refresh_hash,
        token_expires_at=now + timedelta(seconds=settings.token_ttl_seconds),
        created_at=now,
        last_seen_at=now,
    )
    db.add(device)

    audit = AuditLog(
        account_id=account.id,
        device_id=device.id,
        action="account.init",
        created_at=now,
    )
    db.add(audit)

    db.commit()

    return JSONResponse(
        status_code=201,
        content={
            "device_token": raw_token,
            "refresh_token": raw_refresh,
            "device_id": device.id,
            "token_expires_at": device.token_expires_at.isoformat() + "Z",
        },
    )


@router.get("/keys")
def account_keys_get(
    db: Session = Depends(get_db),
    device: Device | None = Depends(optional_token),
) -> JSONResponse:
    if device is None:
        return JSONResponse(
            status_code=401,
            content={"error": {"code": "unauthorized", "message": "Valid token required"}},
        )

    account = db.execute(select(Account)).scalar_one_or_none()
    if account is None:
        return JSONResponse(
            status_code=404,
            content={"error": {"code": "not_found", "message": "Account not initialized"}},
        )

    return JSONResponse(
        status_code=200,
        content={
            "salt": account.salt,
            "argon_memory": account.argon_memory,
            "argon_iterations": account.argon_iterations,
            "argon_parallelism": account.argon_parallelism,
            "argon_version": account.argon_version,
            "nonce_ak": account.nonce_ak,
            "wrapped_ak": account.wrapped_ak,
            "salt_rc": account.salt_rc,
            "nonce_rc": account.nonce_rc,
            "wrapped_ak_rc": account.wrapped_ak_rc,
        },
    )


@router.patch("/keys")
def account_keys_patch(
    body: PatchKeysBody,
    db: Session = Depends(get_db),
    device: Device = Depends(require_device_token),
) -> JSONResponse:
    account = db.execute(select(Account)).scalar_one_or_none()
    if account is None:
        return JSONResponse(
            status_code=404,
            content={"error": {"code": "not_found", "message": "Account not initialized"}},
        )

    account.nonce_ak = body.nonce_ak
    account.wrapped_ak = body.wrapped_ak
    if body.salt is not None:
        account.salt = body.salt

    now = datetime.now(timezone.utc)
    audit = AuditLog(
        account_id=account.id,
        device_id=device.id,
        action="account.keys_updated",
        created_at=now,
    )
    db.add(audit)
    db.commit()

    return JSONResponse(status_code=200, content={"ok": True})
