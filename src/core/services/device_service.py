"""Device management business logic."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from src.core.auth.exceptions import DeviceNotFoundError
from src.core.auth.tokens import (
    generate_device_token,
    generate_enrollment_token,
    generate_refresh_token,
)
from src.core.db.connection import get_session
from src.core.db.repository.audit_repo import AuditRepository, get_audit_repository
from src.core.db.repository.device_repo import DeviceRepository, get_device_repository
from src.enums.audit import AuditAction
from src.models.base import Device
from src.settings import Settings, get_settings


def _parse_ttl(value: str) -> int:
    m = re.fullmatch(r"(\d+)\s*([smhd])", value.strip())
    if not m:
        return int(value)
    amount = int(m.group(1))
    unit = m.group(2)
    return amount * {"s": 1, "m": 60, "h": 3600, "d": 86400}[unit]


class DeviceService:
    def __init__(
        self,
        session: Session,
        device_repo: DeviceRepository,
        audit_repo: AuditRepository,
        settings: Settings,
    ) -> None:
        self.session = session
        self.device_repo = device_repo
        self.audit_repo = audit_repo
        self.settings = settings

    def list_devices(self, device: Device) -> dict:
        devices = self.device_repo.list_by_account(device.account_id)
        return {
            "devices": [
                {
                    "id": d.id,
                    "name": d.name,
                    "last_seen": d.last_seen_at.isoformat() + "Z" if d.last_seen_at else None,
                    "expires_at": d.token_expires_at.isoformat() + "Z",
                    "revoked": d.revoked_at is not None,
                    "created_at": d.created_at.isoformat() + "Z",
                    "allowed_app": d.allowed_app,
                    "allowed_env": d.allowed_env,
                }
                for d in devices
            ]
        }

    def revoke_device(self, device: Device, target_device_id: str) -> dict:
        target = self.device_repo.get_by_id_and_account(
            target_device_id, device.account_id
        )
        if target is None:
            raise DeviceNotFoundError()

        now = datetime.now(timezone.utc)
        target.revoked_at = now

        self.audit_repo.log(
            AuditAction.DEVICE_REVOKED, device.account_id, device.id,
            created_at=now,
            meta=f'{{"revoked_device_id": "{target_device_id}"}}',
        )
        self.session.commit()
        return {"ok": True}

    def create_enroll_token(
        self, device: Device, name: str, ttl: str, kind: str
    ) -> dict:
        ttl_secs = _parse_ttl(ttl)
        now = datetime.now(timezone.utc)

        raw_token, token_hash = generate_enrollment_token()

        enroll_device = Device(
            account_id=device.account_id,
            name=f"enroll:{name}",
            token_hash=token_hash,
            token_expires_at=now + timedelta(seconds=ttl_secs),
            created_at=now,
            # Carry the caller's identity so the device enrolled with this token
            # (e.g. the web admin login) belongs to the same user, not the owner.
            user_id=device.user_id,
        )
        self.device_repo.create(enroll_device)

        self.audit_repo.log(
            AuditAction.ENROLL_TOKEN_ISSUED, device.account_id, device.id,
            created_at=now,
            meta=f'{{"name": "{name}", "kind": "{kind}", "ttl": "{ttl}"}}',
        )
        self.session.commit()

        return {
            "token": raw_token,
            "expires_at": enroll_device.token_expires_at.isoformat() + "Z",
        }


    def create_ci_token(
        self, device: Device, app: str, env: str, ttl: str,
    ) -> dict:
        """Create a scoped CI device token restricted to a specific app+env."""
        ttl_secs = _parse_ttl(ttl)
        now = datetime.now(timezone.utc)

        raw_token, token_hash = generate_device_token()
        raw_refresh, refresh_hash = generate_refresh_token()

        ci_device = Device(
            account_id=device.account_id,
            name=f"ci:{app}/{env}",
            token_hash=token_hash,
            refresh_hash=refresh_hash,
            token_expires_at=now + timedelta(seconds=ttl_secs),
            created_at=now,
            last_seen_at=now,
            user_id=device.user_id,
            allowed_app=app,
            allowed_env=env,
        )
        self.device_repo.create(ci_device)

        self.audit_repo.log(
            AuditAction.ENROLL_TOKEN_ISSUED, device.account_id, device.id,
            created_at=now,
            meta=f'{{"name": "ci:{app}/{env}", "kind": "ci", "app": "{app}", "env": "{env}"}}',
        )
        self.session.commit()

        return {
            "device_token": raw_token,
            "refresh_token": raw_refresh,
            "device_id": ci_device.id,
            "token_expires_at": ci_device.token_expires_at.isoformat() + "Z",
        }


def get_device_service(
    session: Annotated[Session, Depends(get_session)],
    device_repo: Annotated[DeviceRepository, Depends(get_device_repository)],
    audit_repo: Annotated[AuditRepository, Depends(get_audit_repository)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> DeviceService:
    return DeviceService(session, device_repo, audit_repo, settings)
