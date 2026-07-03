"""Account business logic."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Annotated, NamedTuple

from fastapi import Depends
from sqlalchemy.orm import Session

from src.core.auth.exceptions import AccountExistsError, AccountNotFoundError, InvalidBootstrapError, UnauthorizedError
from src.core.auth.tokens import generate_device_token, generate_refresh_token
from src.core.db.connection import get_session
from src.core.db.repository.account_repo import AccountRepository, get_account_repository
from src.core.db.repository.audit_repo import AuditRepository, get_audit_repository
from src.core.db.repository.device_repo import DeviceRepository, get_device_repository
from src.core.db.repository.user_repo import UserRepository, get_user_repository
from src.enums.audit import AuditAction
from src.models.base import Account, Device, User
from src.settings import Settings, get_settings


class AccountInitResult(NamedTuple):
    device_token: str
    refresh_token: str
    device_id: str
    token_expires_at: str


class AccountService:
    def __init__(
        self,
        session: Session,
        account_repo: AccountRepository,
        device_repo: DeviceRepository,
        audit_repo: AuditRepository,
        settings: Settings,
        user_repo: UserRepository,
    ) -> None:
        self.session = session
        self.account_repo = account_repo
        self.device_repo = device_repo
        self.audit_repo = audit_repo
        self.settings = settings
        self.user_repo = user_repo

    def init_account(
        self,
        *,
        bootstrap_secret: str,
        salt: str,
        argon_memory: int,
        argon_iterations: int,
        argon_parallelism: int,
        argon_version: int,
        nonce_ak: str,
        wrapped_ak: str,
        salt_rc: str | None,
        nonce_rc: str | None,
        wrapped_ak_rc: str | None,
        device_name: str,
    ) -> AccountInitResult:
        existing = self.account_repo.get_account()
        if existing is not None:
            raise AccountExistsError()

        if bootstrap_secret != self.settings.BOOTSTRAP_SECRET:
            raise InvalidBootstrapError()

        now = datetime.now(timezone.utc)

        account = Account(
            salt=salt,
            argon_memory=argon_memory,
            argon_iterations=argon_iterations,
            argon_parallelism=argon_parallelism,
            argon_version=argon_version,
            nonce_ak=nonce_ak,
            wrapped_ak=wrapped_ak,
            salt_rc=salt_rc,
            nonce_rc=nonce_rc,
            wrapped_ak_rc=wrapped_ak_rc,
            bootstrap_secret_hash=self.settings.bootstrap_secret_hash,
            bootstrap_used=True,
            created_at=now,
        )
        self.account_repo.create(account)
        self.session.flush()

        # Team model (spec E.9): the account is a team of one from day one.
        owner = User(
            account_id=account.id,
            name="owner",
            role="owner",
            salt=salt,
            argon_memory=argon_memory,
            argon_iterations=argon_iterations,
            argon_parallelism=argon_parallelism,
            argon_version=argon_version,
            nonce_ak=nonce_ak,
            wrapped_ak=wrapped_ak,
            salt_rc=salt_rc,
            nonce_rc=nonce_rc,
            wrapped_ak_rc=wrapped_ak_rc,
            key_gen=1,
            created_at=now,
        )
        self.user_repo.create(owner)

        raw_token, token_hash = generate_device_token()
        raw_refresh, refresh_hash = generate_refresh_token()

        device = Device(
            account_id=account.id,
            name=device_name,
            token_hash=token_hash,
            refresh_hash=refresh_hash,
            token_expires_at=now + timedelta(seconds=self.settings.token_ttl_seconds),
            created_at=now,
            last_seen_at=now,
            user_id=owner.id,
        )
        self.device_repo.create(device)

        self.audit_repo.log(
            AuditAction.ACCOUNT_INIT, account.id, device.id, created_at=now
        )

        self.session.commit()

        return AccountInitResult(
            device_token=raw_token,
            refresh_token=raw_refresh,
            device_id=device.id,
            token_expires_at=device.token_expires_at.isoformat() + "Z",
        )

    def get_keys(self, device: Device | None) -> dict:
        if device is None:
            raise UnauthorizedError()

        account = self.account_repo.get_account()
        if account is None:
            raise AccountNotFoundError()

        # Source of truth is the requesting device's user row (spec K.0);
        # fall back to the account row for pre-migration devices.
        user = self.user_repo.get_by_id(device.user_id) if device.user_id else None
        if user is None:
            user = self.user_repo.owner_of(account.id)
        src = user if user is not None else account
        key_gen = user.key_gen if user is not None else account.current_key_gen

        return {
            "salt": src.salt,
            "argon_memory": src.argon_memory,
            "argon_iterations": src.argon_iterations,
            "argon_parallelism": src.argon_parallelism,
            "argon_version": src.argon_version,
            "nonce_ak": src.nonce_ak,
            "wrapped_ak": src.wrapped_ak,
            "salt_rc": src.salt_rc,
            "nonce_rc": src.nonce_rc,
            "wrapped_ak_rc": src.wrapped_ak_rc,
            "key_gen": key_gen,
        }

    def patch_keys(
        self,
        device: Device,
        *,
        nonce_ak: str,
        wrapped_ak: str,
        salt: str | None,
    ) -> dict:
        account = self.account_repo.get_account()
        if account is None:
            raise AccountNotFoundError()

        account.nonce_ak = nonce_ak
        account.wrapped_ak = wrapped_ak
        if salt is not None:
            account.salt = salt

        # Dual-write into the user row (source of truth going forward).
        user = self.user_repo.get_by_id(device.user_id) if device.user_id else None
        if user is None:
            user = self.user_repo.owner_of(account.id)
        if user is not None:
            user.nonce_ak = nonce_ak
            user.wrapped_ak = wrapped_ak
            if salt is not None:
                user.salt = salt

        now = datetime.now(timezone.utc)
        self.audit_repo.log(
            AuditAction.ACCOUNT_KEYS_UPDATED, account.id, device.id, created_at=now
        )

        self.session.commit()
        return {"ok": True}


def get_account_service(
    session: Annotated[Session, Depends(get_session)],
    account_repo: Annotated[AccountRepository, Depends(get_account_repository)],
    device_repo: Annotated[DeviceRepository, Depends(get_device_repository)],
    audit_repo: Annotated[AuditRepository, Depends(get_audit_repository)],
    settings: Annotated[Settings, Depends(get_settings)],
    user_repo: Annotated[UserRepository, Depends(get_user_repository)],
) -> AccountService:
    return AccountService(
        session, account_repo, device_repo, audit_repo, settings, user_repo
    )
