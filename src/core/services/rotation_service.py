"""AK rotation business logic (spec L)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

from fastapi import Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.core.auth.exceptions import (
    AccountNotFoundError,
    AppOrEnvNotFoundError,
    RevisionNotFoundError,
    RotationConflictError,
    RotationIncompleteError,
    RotationNotActiveError,
)
from src.core.db.connection import get_session
from src.core.db.repository.account_repo import AccountRepository, get_account_repository
from src.core.db.repository.app_repo import AppRepository, get_app_repository
from src.core.db.repository.audit_repo import AuditRepository, get_audit_repository
from src.core.db.repository.environment_repo import (
    EnvironmentRepository,
    get_environment_repository,
)
from src.core.db.repository.revision_repo import (
    RevisionRepository,
    get_revision_repository,
)
from src.enums.audit import AuditAction
from src.models.base import App, Device, Environment, Revision

STALE_PAGE_LIMIT = 500


class RotationService:
    def __init__(
        self,
        session: Session,
        account_repo: AccountRepository,
        app_repo: AppRepository,
        env_repo: EnvironmentRepository,
        revision_repo: RevisionRepository,
        audit_repo: AuditRepository,
    ) -> None:
        self.session = session
        self.account_repo = account_repo
        self.app_repo = app_repo
        self.env_repo = env_repo
        self.revision_repo = revision_repo
        self.audit_repo = audit_repo

    def _account(self):
        account = self.account_repo.get_account()
        if account is None:
            raise AccountNotFoundError()
        return account

    def _stale_query(self, account_id: str, new_gen: int):
        return (
            select(Revision, Environment.name, App.name)
            .join(Environment, Revision.environment_id == Environment.id)
            .join(App, Environment.app_id == App.id)
            .where(App.account_id == account_id, Revision.key_gen < new_gen)
        )

    def _stale_count(self, account_id: str, new_gen: int) -> int:
        return self.session.execute(
            select(func.count())
            .select_from(Revision)
            .join(Environment, Revision.environment_id == Environment.id)
            .join(App, Environment.app_id == App.id)
            .where(App.account_id == account_id, Revision.key_gen < new_gen)
        ).scalar_one()

    def begin(self, device: Device, body) -> dict:
        account = self._account()

        if account.rotation_new_gen is not None:
            # Idempotent re-begin with the same target generation (resume).
            if account.rotation_new_gen == body.new_key_gen:
                return {
                    "new_key_gen": account.rotation_new_gen,
                    "stale_count": self._stale_count(account.id, account.rotation_new_gen),
                }
            raise RotationConflictError(
                f"another rotation to gen {account.rotation_new_gen} is in progress"
            )

        if body.new_key_gen != account.current_key_gen + 1:
            raise RotationConflictError(
                f"new_key_gen must be {account.current_key_gen + 1}"
            )

        account.rotation_new_gen = body.new_key_gen
        account.rot_nonce_ak = body.nonce_ak
        account.rot_wrapped_ak = body.wrapped_ak
        account.rot_salt_rc = body.salt_rc
        account.rot_nonce_rc = body.nonce_rc
        account.rot_wrapped_ak_rc = body.wrapped_ak_rc

        stale = self._stale_count(account.id, body.new_key_gen)
        now = datetime.now(timezone.utc)
        self.audit_repo.log(
            AuditAction.ROTATE_BEGIN, account.id, device.id,
            created_at=now, meta=f'{{"new_gen": {body.new_key_gen}, "stale": {stale}}}',
        )
        self.session.commit()
        return {"new_key_gen": body.new_key_gen, "stale_count": stale}

    def status(self, device: Device) -> dict:
        account = self._account()
        if account.rotation_new_gen is None:
            return {
                "in_progress": False,
                "current_key_gen": account.current_key_gen,
            }

        new_gen = account.rotation_new_gen
        rows = self.session.execute(
            self._stale_query(account.id, new_gen).limit(STALE_PAGE_LIMIT)
        ).all()
        return {
            "in_progress": True,
            "current_key_gen": account.current_key_gen,
            "new_key_gen": new_gen,
            "stale_count": self._stale_count(account.id, new_gen),
            "stale": [
                {"app": app_name, "env": env_name, "rev_number": rev.rev_number}
                for rev, env_name, app_name in rows
            ],
            "pending_nonce_ak": account.rot_nonce_ak,
            "pending_wrapped_ak": account.rot_wrapped_ak,
        }

    def put_blob(
        self, device: Device, app_name: str, env_name: str, rev: int, body
    ) -> dict:
        account = self._account()
        if account.rotation_new_gen is None:
            raise RotationNotActiveError()
        if body.key_gen != account.rotation_new_gen:
            raise RotationConflictError(
                f"key_gen must be {account.rotation_new_gen}"
            )

        app = self.app_repo.get_by_account_and_name(account.id, app_name)
        if app is None:
            raise AppOrEnvNotFoundError()
        env = self.env_repo.get_by_app_and_name(app.id, env_name)
        if env is None:
            raise AppOrEnvNotFoundError()
        revision = self.revision_repo.get_by_env_and_number(env.id, rev)
        if revision is None:
            raise RevisionNotFoundError(rev)

        revision.blob = body.blob
        revision.key_gen = body.key_gen

        now = datetime.now(timezone.utc)
        self.audit_repo.log(
            AuditAction.ROTATE_BLOB, account.id, device.id,
            app_name=app_name, env_name=env_name, rev_number=rev, created_at=now,
        )
        self.session.commit()
        return {"rev_number": rev, "key_gen": body.key_gen}

    def complete(self, device: Device) -> dict:
        account = self._account()
        if account.rotation_new_gen is None:
            raise RotationNotActiveError()

        new_gen = account.rotation_new_gen
        stale = self._stale_count(account.id, new_gen)
        if stale > 0:
            raise RotationIncompleteError(stale)

        # Cut over: the pending wraps become the account's live wraps.
        account.current_key_gen = new_gen
        account.nonce_ak = account.rot_nonce_ak
        account.wrapped_ak = account.rot_wrapped_ak
        if account.rot_wrapped_ak_rc is not None:
            account.salt_rc = account.rot_salt_rc
            account.nonce_rc = account.rot_nonce_rc
            account.wrapped_ak_rc = account.rot_wrapped_ak_rc
        account.rotation_new_gen = None
        account.rot_nonce_ak = None
        account.rot_wrapped_ak = None
        account.rot_salt_rc = None
        account.rot_nonce_rc = None
        account.rot_wrapped_ak_rc = None

        now = datetime.now(timezone.utc)
        self.audit_repo.log(
            AuditAction.ROTATE_COMPLETE, account.id, device.id,
            created_at=now, meta=f'{{"new_gen": {new_gen}}}',
        )
        self.session.commit()
        return {"current_key_gen": new_gen}


def rotation_active(session: Session, account_repo: AccountRepository) -> bool:
    account = account_repo.get_account()
    return account is not None and account.rotation_new_gen is not None


def get_rotation_service(
    session: Annotated[Session, Depends(get_session)],
    account_repo: Annotated[AccountRepository, Depends(get_account_repository)],
    app_repo: Annotated[AppRepository, Depends(get_app_repository)],
    env_repo: Annotated[EnvironmentRepository, Depends(get_environment_repository)],
    revision_repo: Annotated[RevisionRepository, Depends(get_revision_repository)],
    audit_repo: Annotated[AuditRepository, Depends(get_audit_repository)],
) -> RotationService:
    return RotationService(
        session, account_repo, app_repo, env_repo, revision_repo, audit_repo
    )
