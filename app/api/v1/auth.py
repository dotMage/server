"""Auth endpoints: device registration and token refresh."""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import generate_device_token, generate_refresh_token
from app.core.config import settings
from app.core.ratelimit import check_rate_limit
from app.db.models import AuditLog, Device
from app.db.session import get_db

router = APIRouter(prefix="/auth", tags=["auth"])


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


class DeviceRegisterBody(BaseModel):
    device_name: str = "cli"


class RefreshBody(BaseModel):
    refresh_token: str


@router.post("/device")
def auth_device(
    body: DeviceRegisterBody,
    request: Request,
    authorization: str | None = Header(None),
    db: Session = Depends(get_db),
    _rl: None = Depends(check_rate_limit),
) -> JSONResponse:
    """Register a new device using an enrollment token."""
    if not authorization:
        return JSONResponse(
            status_code=401,
            content={"error": {"code": "unauthorized", "message": "Enrollment token required"}},
        )

    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return JSONResponse(
            status_code=401,
            content={"error": {"code": "unauthorized", "message": "Invalid Authorization header"}},
        )

    raw_token = parts[1]
    token_hash = _sha256(raw_token)

    # Find enrollment device
    enroll_device = db.execute(
        select(Device).where(Device.token_hash == token_hash)
    ).scalar_one_or_none()

    if enroll_device is None:
        return JSONResponse(
            status_code=401,
            content={"error": {"code": "unauthorized", "message": "Invalid enrollment token"}},
        )

    if enroll_device.revoked_at is not None:
        return JSONResponse(
            status_code=401,
            content={"error": {"code": "token_revoked", "message": "Enrollment token has been revoked"}},
        )

    now = datetime.now(timezone.utc)
    expires = enroll_device.token_expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires < now:
        return JSONResponse(
            status_code=401,
            content={"error": {"code": "token_expired", "message": "Enrollment token has expired"}},
        )

    account_id = enroll_device.account_id

    # Revoke the enrollment token (single-use)
    enroll_device.revoked_at = now

    # Create the new device
    new_raw_token, new_token_hash = generate_device_token()
    new_raw_refresh, new_refresh_hash = generate_refresh_token()

    device = Device(
        account_id=account_id,
        name=body.device_name,
        token_hash=new_token_hash,
        refresh_hash=new_refresh_hash,
        token_expires_at=now + timedelta(seconds=settings.token_ttl_seconds),
        created_at=now,
        last_seen_at=now,
    )
    db.add(device)

    audit = AuditLog(
        account_id=account_id,
        device_id=device.id,
        action="device.registered",
        created_at=now,
    )
    db.add(audit)
    db.commit()

    return JSONResponse(
        status_code=201,
        content={
            "device_token": new_raw_token,
            "refresh_token": new_raw_refresh,
            "device_id": device.id,
            "token_expires_at": device.token_expires_at.isoformat() + "Z",
        },
    )


@router.post("/refresh")
def auth_refresh(
    body: RefreshBody,
    request: Request,
    db: Session = Depends(get_db),
    _rl: None = Depends(check_rate_limit),
) -> JSONResponse:
    """Rotate device and refresh tokens."""
    refresh_hash = _sha256(body.refresh_token)

    device = db.execute(
        select(Device).where(Device.refresh_hash == refresh_hash)
    ).scalar_one_or_none()

    if device is None:
        return JSONResponse(
            status_code=401,
            content={"error": {"code": "unauthorized", "message": "Invalid refresh token"}},
        )

    if device.revoked_at is not None:
        return JSONResponse(
            status_code=401,
            content={"error": {"code": "device_revoked", "message": "Device has been revoked"}},
        )

    now = datetime.now(timezone.utc)

    # Generate new tokens
    new_raw_token, new_token_hash = generate_device_token()
    new_raw_refresh, new_refresh_hash = generate_refresh_token()

    device.token_hash = new_token_hash
    device.refresh_hash = new_refresh_hash
    device.token_expires_at = now + timedelta(seconds=settings.token_ttl_seconds)
    device.last_seen_at = now

    db.commit()

    return JSONResponse(
        status_code=200,
        content={
            "device_token": new_raw_token,
            "refresh_token": new_raw_refresh,
            "device_id": device.id,
            "token_expires_at": device.token_expires_at.isoformat() + "Z",
        },
    )
