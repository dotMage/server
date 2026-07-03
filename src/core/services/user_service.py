"""Team users & invitations business logic (spec K, Phase 3)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from src.core.auth.exceptions import (
    AccountNotFoundError,
    InvitationInvalidError,
    LastOwnerError,
    NotAnOwnerError,
    RotationInProgressError,
    UserExistsError,
    UserNotFoundError,
)
from src.core.auth.tokens import generate_device_token, generate_refresh_token, sha256_hash
from src.core.db.connection import get_session
from src.core.db.repository.account_repo import AccountRepository, get_account_repository
from src.core.db.repository.audit_repo import AuditRepository, get_audit_repository
from src.core.db.repository.device_repo import DeviceRepository, get_device_repository
from src.core.db.repository.invitation_repo import (
    InvitationRepository,
    get_invitation_repository,
)
from src.core.db.repository.user_repo import UserRepository, get_user_repository
from src.enums.audit import AuditAction
from src.models.base import Device, Invitation, User
from src.settings import Settings, get_settings

REDEEM_GRACE = timedelta(minutes=15)


def _parse_ttl(ttl: str) -> timedelta:
    ttl = ttl.strip().lower()
    if ttl.endswith("d"):
        return timedelta(days=int(ttl[:-1]))
    if ttl.endswith("h"):
        return timedelta(hours=int(ttl[:-1]))
    if ttl.endswith("m"):
        return timedelta(minutes=int(ttl[:-1]))
    if ttl.endswith("s"):
        return timedelta(seconds=int(ttl[:-1]))
    return timedelta(seconds=int(ttl))


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


class UserService:
    def __init__(
        self,
        session: Session,
        account_repo: AccountRepository,
        user_repo: UserRepository,
        invitation_repo: InvitationRepository,
        device_repo: DeviceRepository,
        audit_repo: AuditRepository,
        settings: Settings,
    ) -> None:
        self.session = session
        self.account_repo = account_repo
        self.user_repo = user_repo
        self.invitation_repo = invitation_repo
        self.device_repo = device_repo
        self.audit_repo = audit_repo
        self.settings = settings

    def _account(self):
        account = self.account_repo.get_account()
        if account is None:
            raise AccountNotFoundError()
        return account

    def _acting_user(self, device: Device) -> User | None:
        user = self.user_repo.get_by_id(device.user_id) if device.user_id else None
        if user is None:
            user = self.user_repo.owner_of(device.account_id)
        return user

    def list_users(self, device: Device) -> dict:
        account = self._account()
        users = self.user_repo.list_by_account(account.id)
        invitations = self.invitation_repo.list_pending(account.id)
        now = datetime.now(timezone.utc)
        return {
            "users": [
                {
                    "id": u.id,
                    "name": u.name,
                    "role": u.role,
                    "status": u.status,
                    "key_gen": u.key_gen,
                    "created_at": u.created_at.isoformat() + "Z",
                }
                for u in users
            ],
            "invitations": [
                {
                    "id": i.id,
                    "name": i.name,
                    "role": i.role,
                    "status": "expired" if _aware(i.expires_at) < now else i.status,
                    "expires_at": i.expires_at.isoformat() + "Z",
                }
                for i in invitations
            ],
        }

    def invite(self, device: Device, body) -> dict:
        account = self._account()
        if account.rotation_new_gen is not None:
            # A sealed AK from mid-rotation could go stale before redemption.
            raise RotationInProgressError()

        actor = self._acting_user(device)
        if actor is None or actor.role != "owner":
            raise NotAnOwnerError()

        if self.user_repo.get_by_account_and_name(account.id, body.name):
            raise UserExistsError(body.name)

        now = datetime.now(timezone.utc)
        invitation = Invitation(
            account_id=account.id,
            name=body.name,
            role=body.role,
            redeem_hash=body.redeem_hash,
            sealed_ak=body.sealed_ak,
            nonce_inv=body.nonce_inv,
            key_gen=account.current_key_gen,
            status="pending",
            created_by=actor.id,
            expires_at=now + _parse_ttl(body.ttl),
            created_at=now,
        )
        self.invitation_repo.create(invitation)

        self.audit_repo.log(
            AuditAction.USER_INVITED, account.id, device.id,
            created_at=now, meta=f'{{"name": "{body.name}", "role": "{body.role}"}}',
            user_id=actor.id,
        )
        self.session.commit()
        return {
            "invitation_id": invitation.id,
            "expires_at": invitation.expires_at.isoformat() + "Z",
        }

    def _valid_invitation(self, invitation_id: str, redeem_secret: str) -> Invitation:
        invitation = self.invitation_repo.get_by_id(invitation_id)
        if invitation is None:
            raise InvitationInvalidError()
        if invitation.status not in ("pending", "redeeming"):
            raise InvitationInvalidError()
        if _aware(invitation.expires_at) < datetime.now(timezone.utc):
            raise InvitationInvalidError()
        if sha256_hash(redeem_secret) != invitation.redeem_hash:
            raise InvitationInvalidError()
        return invitation

    def redeem(self, body) -> dict:
        """Step 1 (spec K.2): hand out the sealed AK."""
        invitation = self._valid_invitation(body.invitation_id, body.redeem_secret)
        account = self._account()

        invitation.status = "redeeming"
        # Redeeming state expires quickly so an abandoned step 2 self-heals.
        invitation.expires_at = min(
            _aware(invitation.expires_at),
            datetime.now(timezone.utc) + REDEEM_GRACE,
        )
        self.session.commit()
        return {
            "sealed_ak": invitation.sealed_ak,
            "nonce_inv": invitation.nonce_inv,
            "key_gen": invitation.key_gen,
            "name": invitation.name,
            "role": invitation.role,
            "argon_defaults": {
                "memory": account.argon_memory,
                "iterations": account.argon_iterations,
                "parallelism": account.argon_parallelism,
                "version": account.argon_version,
            },
        }

    def complete(self, body) -> dict:
        """Step 2 (spec K.2): create the user + first device, burn the invite."""
        invitation = self._valid_invitation(body.invitation_id, body.redeem_secret)
        account = self._account()

        if self.user_repo.get_by_account_and_name(account.id, invitation.name):
            raise UserExistsError(invitation.name)

        now = datetime.now(timezone.utc)
        user = User(
            account_id=account.id,
            name=invitation.name,
            role=invitation.role,
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
            key_gen=invitation.key_gen,
            created_at=now,
        )
        self.user_repo.create(user)

        raw_token, token_hash = generate_device_token()
        raw_refresh, refresh_hash = generate_refresh_token()
        device = Device(
            account_id=account.id,
            name=body.device_name,
            token_hash=token_hash,
            refresh_hash=refresh_hash,
            token_expires_at=now + timedelta(seconds=self.settings.token_ttl_seconds),
            created_at=now,
            last_seen_at=now,
            user_id=user.id,
        )
        self.device_repo.create(device)

        invitation.status = "used"
        invitation.sealed_ak = None
        invitation.nonce_inv = None

        self.audit_repo.log(
            AuditAction.USER_JOINED, account.id, device.id,
            created_at=now, meta=f'{{"name": "{user.name}", "role": "{user.role}"}}',
            user_id=user.id,
        )
        self.session.commit()

        return {
            "user_id": user.id,
            "device_id": device.id,
            "device_token": raw_token,
            "refresh_token": raw_refresh,
            "expires_at": device.token_expires_at.isoformat() + "Z",
        }


    def _other_active_owner_exists(self, account_id: str, user_id: str) -> bool:
        return any(
            u.role == "owner" and u.status == "active" and u.id != user_id
            for u in self.user_repo.list_by_account(account_id)
        )

    def change_role(self, device: Device, user_id: str, role: str) -> dict:
        account = self._account()
        target = self.user_repo.get_by_id(user_id)
        if target is None or target.account_id != account.id:
            raise UserNotFoundError()
        if (
            target.role == "owner"
            and role != "owner"
            and not self._other_active_owner_exists(account.id, target.id)
        ):
            raise LastOwnerError()
        target.role = role
        now = datetime.now(timezone.utc)
        self.audit_repo.log(
            AuditAction.USER_ROLE_CHANGED, account.id, device.id,
            created_at=now, meta=f'{{"name": "{target.name}", "role": "{role}"}}',
        )
        self.session.commit()
        return {"id": target.id, "name": target.name, "role": target.role}

    def remove_user(self, device: Device, user_id: str) -> dict:
        """Offboarding (spec K.5 / Phase 5): drop wraps, revoke devices.
        The caller is told to rotate the key — removal alone is not enough."""
        account = self._account()
        target = self.user_repo.get_by_id(user_id)
        if target is None or target.account_id != account.id:
            raise UserNotFoundError()
        if target.role == "owner" and not self._other_active_owner_exists(
            account.id, target.id
        ):
            raise LastOwnerError()

        now = datetime.now(timezone.utc)
        # Wraps gone: the server can no longer hand this user the AK.
        target.status = "removed"
        target.removed_at = now
        target.wrapped_ak = ""
        target.nonce_ak = ""
        target.salt_rc = None
        target.nonce_rc = None
        target.wrapped_ak_rc = None

        revoked = 0
        for dev in self.device_repo.list_by_account(account.id):
            if dev.user_id == target.id and dev.revoked_at is None:
                dev.revoked_at = now
                revoked += 1

        self.audit_repo.log(
            AuditAction.USER_REMOVED, account.id, device.id,
            created_at=now, meta=f'{{"name": "{target.name}", "devices_revoked": {revoked}}}',
        )
        self.session.commit()
        return {
            "id": target.id,
            "name": target.name,
            "devices_revoked": revoked,
            "rotation_required": True,
        }


def get_user_service(
    session: Annotated[Session, Depends(get_session)],
    account_repo: Annotated[AccountRepository, Depends(get_account_repository)],
    user_repo: Annotated[UserRepository, Depends(get_user_repository)],
    invitation_repo: Annotated[InvitationRepository, Depends(get_invitation_repository)],
    device_repo: Annotated[DeviceRepository, Depends(get_device_repository)],
    audit_repo: Annotated[AuditRepository, Depends(get_audit_repository)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> UserService:
    return UserService(
        session, account_repo, user_repo, invitation_repo, device_repo, audit_repo, settings
    )
