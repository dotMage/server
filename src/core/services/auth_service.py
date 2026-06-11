"""Auth business logic: device registration and token refresh."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from src.core.auth.exceptions import (
    AccountNotFoundError,
    DeviceRevokedError,
    EnrollmentTokenExpiredError,
    EnrollmentTokenRequiredError,
    EnrollmentTokenRevokedError,
    InvalidBootstrapError,
    InvalidEnrollmentTokenError,
    InvalidRefreshTokenError,
)
from src.core.auth.tokens import generate_device_token, generate_refresh_token, sha256_hash
from src.core.db.connection import get_session
from src.core.db.repository.account_repo import AccountRepository, get_account_repository
from src.core.db.repository.audit_repo import AuditRepository, get_audit_repository
from src.core.db.repository.device_repo import DeviceRepository, get_device_repository
from src.enums.audit import AuditAction
from src.models.base import Device
from src.settings import Settings, get_settings


class AuthService:
    def __init__(
        self,
        session: Session,
        account_repo: AccountRepository,
        device_repo: DeviceRepository,
        audit_repo: AuditRepository,
        settings: Settings,
    ) -> None:
        self.session = session
        self.account_repo = account_repo
        self.device_repo = device_repo
        self.audit_repo = audit_repo
        self.settings = settings

    def register_device(
        self,
        authorization: str | None,
        device_name: str,
    ) -> dict:
        if not authorization:
            raise EnrollmentTokenRequiredError()

        parts = authorization.split(" ", 1)
        if len(parts) != 2 or parts[0].lower() != "bearer":
            raise EnrollmentTokenRequiredError()

        raw_token = parts[1]
        token_hash = sha256_hash(raw_token)

        enroll_device = self.device_repo.get_by_token_hash(token_hash)
        if enroll_device is None:
            raise InvalidEnrollmentTokenError()

        if enroll_device.revoked_at is not None:
            raise EnrollmentTokenRevokedError()

        now = datetime.now(timezone.utc)
        expires = enroll_device.token_expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if expires < now:
            raise EnrollmentTokenExpiredError()

        account_id = enroll_device.account_id

        # Revoke the enrollment token (single-use)
        enroll_device.revoked_at = now

        # Create the new device
        new_raw_token, new_token_hash = generate_device_token()
        new_raw_refresh, new_refresh_hash = generate_refresh_token()

        device = Device(
            account_id=account_id,
            name=device_name,
            token_hash=new_token_hash,
            refresh_hash=new_refresh_hash,
            token_expires_at=now + timedelta(seconds=self.settings.token_ttl_seconds),
            created_at=now,
            last_seen_at=now,
        )
        self.device_repo.create(device)

        self.audit_repo.log(
            AuditAction.DEVICE_REGISTERED, account_id, device.id,
            created_at=now,
        )
        self.session.commit()

        return {
            "device_token": new_raw_token,
            "refresh_token": new_raw_refresh,
            "device_id": device.id,
            "token_expires_at": device.token_expires_at.isoformat() + "Z",
        }

    def refresh_token(self, refresh_token_raw: str) -> dict:
        refresh_hash = sha256_hash(refresh_token_raw)

        device = self.device_repo.get_by_refresh_hash(refresh_hash)
        if device is None:
            raise InvalidRefreshTokenError()

        if device.revoked_at is not None:
            raise DeviceRevokedError()

        now = datetime.now(timezone.utc)

        new_raw_token, new_token_hash = generate_device_token()
        new_raw_refresh, new_refresh_hash = generate_refresh_token()

        device.token_hash = new_token_hash
        device.refresh_hash = new_refresh_hash
        device.token_expires_at = now + timedelta(seconds=self.settings.token_ttl_seconds)
        device.last_seen_at = now

        self.session.commit()

        return {
            "device_token": new_raw_token,
            "refresh_token": new_raw_refresh,
            "device_id": device.id,
            "token_expires_at": device.token_expires_at.isoformat() + "Z",
        }


    def register_device_with_bootstrap(
        self,
        bootstrap_secret: str,
        device_name: str,
    ) -> dict:
        """Register a new device using the bootstrap secret."""
        account = self.account_repo.get_account()
        if account is None:
            raise AccountNotFoundError()

        # Compare against Account's stored hash (persistent in DB),
        # NOT settings.BOOTSTRAP_SECRET (may change after server restart)
        provided_hash = sha256_hash(bootstrap_secret)
        if provided_hash != account.bootstrap_secret_hash:
            raise InvalidBootstrapError()

        now = datetime.now(timezone.utc)
        new_raw_token, new_token_hash = generate_device_token()
        new_raw_refresh, new_refresh_hash = generate_refresh_token()

        device = Device(
            account_id=account.id,
            name=device_name,
            token_hash=new_token_hash,
            refresh_hash=new_refresh_hash,
            token_expires_at=now + timedelta(seconds=self.settings.token_ttl_seconds),
            created_at=now,
            last_seen_at=now,
        )
        self.device_repo.create(device)

        self.audit_repo.log(
            AuditAction.DEVICE_REGISTERED, account.id, device.id, created_at=now,
        )
        self.session.commit()

        return {
            "device_token": new_raw_token,
            "refresh_token": new_raw_refresh,
            "device_id": device.id,
            "token_expires_at": device.token_expires_at.isoformat() + "Z",
        }


def get_auth_service(
    session: Annotated[Session, Depends(get_session)],
    account_repo: Annotated[AccountRepository, Depends(get_account_repository)],
    device_repo: Annotated[DeviceRepository, Depends(get_device_repository)],
    audit_repo: Annotated[AuditRepository, Depends(get_audit_repository)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthService:
    return AuthService(session, account_repo, device_repo, audit_repo, settings)
