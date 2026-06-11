"""FastAPI dependencies for authentication."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import Depends, Header
from sqlalchemy.orm import Session

from src.core.auth.exceptions import (
    DeviceRevokedError,
    DeviceScopeError,
    InvalidTokenError,
    NotAuthenticatedError,
    TokenExpiredError,
)
from src.core.auth.tokens import sha256_hash
from src.core.db.connection import get_session
from src.core.db.repository.device_repo import DeviceRepository, get_device_repository
from src.models.base import Device


def _extract_bearer(authorization: str | None) -> str | None:
    if not authorization:
        return None
    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    return parts[1]


def require_device_token(
    authorization: str | None = Header(None),
    session: Session = Depends(get_session),
    device_repo: DeviceRepository = Depends(get_device_repository),
) -> Device:
    """FastAPI dependency: require a valid device token."""
    raw_token = _extract_bearer(authorization)
    if not raw_token:
        raise NotAuthenticatedError()

    token_hash = sha256_hash(raw_token)
    device = device_repo.get_by_token_hash(token_hash)

    if device is None:
        raise InvalidTokenError()

    if device.revoked_at is not None:
        raise DeviceRevokedError()

    now = datetime.now(timezone.utc)
    expires = device.token_expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires < now:
        raise TokenExpiredError()

    device.last_seen_at = now
    session.commit()

    return device


def optional_token(
    authorization: str | None = Header(None),
    session: Session = Depends(get_session),
    device_repo: DeviceRepository = Depends(get_device_repository),
) -> Device | None:
    """Accept any valid token. Returns None if no auth header or invalid."""
    raw_token = _extract_bearer(authorization)
    if not raw_token:
        return None

    token_hash = sha256_hash(raw_token)
    device = device_repo.get_by_token_hash(token_hash)

    if device is None:
        return None

    if device.revoked_at is not None:
        return None

    now = datetime.now(timezone.utc)
    expires = device.token_expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires < now:
        return None

    device.last_seen_at = now
    session.commit()
    return device


def check_device_scope(device: Device, app_name: str, env_name: str | None = None) -> None:
    """Raise DeviceScopeError if device is scoped and doesn't match the request."""
    if device.allowed_app is not None and device.allowed_app != app_name:
        raise DeviceScopeError()
    if device.allowed_env is not None and env_name is not None and device.allowed_env != env_name:
        raise DeviceScopeError()
