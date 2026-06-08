"""Device management: list, revoke, enroll-token."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import generate_enrollment_token, require_device_token
from app.db.models import AuditLog, Device
from app.db.session import get_db

router = APIRouter(prefix="/devices", tags=["devices"])


class EnrollTokenBody(BaseModel):
    name: str = "new-device"
    ttl: str = "1h"
    kind: str = "enrollment"


def _parse_ttl(value: str) -> int:
    import re

    m = re.fullmatch(r"(\d+)\s*([smhd])", value.strip())
    if not m:
        return int(value)
    amount = int(m.group(1))
    unit = m.group(2)
    return amount * {"s": 1, "m": 60, "h": 3600, "d": 86400}[unit]


@router.get("")
def devices_list(
    db: Session = Depends(get_db),
    device: Device = Depends(require_device_token),
) -> JSONResponse:
    devices = (
        db.execute(select(Device).where(Device.account_id == device.account_id))
        .scalars()
        .all()
    )

    return JSONResponse(
        status_code=200,
        content={
            "devices": [
                {
                    "id": d.id,
                    "name": d.name,
                    "last_seen": d.last_seen_at.isoformat() + "Z" if d.last_seen_at else None,
                    "expires_at": d.token_expires_at.isoformat() + "Z",
                    "revoked": d.revoked_at is not None,
                    "created_at": d.created_at.isoformat() + "Z",
                }
                for d in devices
            ]
        },
    )


@router.delete("/{device_id}")
def devices_revoke(
    device_id: str,
    db: Session = Depends(get_db),
    device: Device = Depends(require_device_token),
) -> JSONResponse:
    target = db.execute(
        select(Device).where(
            Device.id == device_id,
            Device.account_id == device.account_id,
        )
    ).scalar_one_or_none()

    if target is None:
        return JSONResponse(
            status_code=404,
            content={"error": {"code": "not_found", "message": "Device not found"}},
        )

    now = datetime.now(timezone.utc)
    target.revoked_at = now

    audit = AuditLog(
        account_id=device.account_id,
        device_id=device.id,
        action="device.revoked",
        created_at=now,
        meta=f'{{"revoked_device_id": "{device_id}"}}',
    )
    db.add(audit)
    db.commit()

    return JSONResponse(status_code=200, content={"ok": True})


@router.post("/enroll-token")
def devices_enroll_token(
    body: EnrollTokenBody,
    db: Session = Depends(get_db),
    device: Device = Depends(require_device_token),
) -> JSONResponse:
    ttl_secs = _parse_ttl(body.ttl)
    now = datetime.now(timezone.utc)

    raw_token, token_hash = generate_enrollment_token()

    # Create a device record for the enrollment token
    enroll_device = Device(
        account_id=device.account_id,
        name=f"enroll:{body.name}",
        token_hash=token_hash,
        token_expires_at=now + timedelta(seconds=ttl_secs),
        created_at=now,
    )
    db.add(enroll_device)

    audit = AuditLog(
        account_id=device.account_id,
        device_id=device.id,
        action="enroll_token.issued",
        created_at=now,
        meta=f'{{"name": "{body.name}", "kind": "{body.kind}", "ttl": "{body.ttl}"}}',
    )
    db.add(audit)
    db.commit()

    return JSONResponse(
        status_code=201,
        content={
            "token": raw_token,
            "expires_at": enroll_device.token_expires_at.isoformat() + "Z",
        },
    )
