"""Revision business logic."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from src.core.auth.exceptions import (
    AppOrEnvNotFoundError,
    BadRevisionError,
    RevisionConflictError,
    RevisionNotFoundError,
    RotationInProgressError,
)
from src.core.db.connection import get_session
from src.core.db.repository.account_repo import AccountRepository, get_account_repository
from src.core.db.repository.app_repo import AppRepository, get_app_repository
from src.core.db.repository.audit_repo import AuditRepository, get_audit_repository
from src.core.db.repository.environment_repo import EnvironmentRepository, get_environment_repository
from src.core.db.repository.revision_repo import RevisionRepository, get_revision_repository
from src.enums.audit import AuditAction
from src.models.base import App, Device, Environment, Revision


class RevisionService:
    def __init__(
        self,
        session: Session,
        app_repo: AppRepository,
        env_repo: EnvironmentRepository,
        revision_repo: RevisionRepository,
        audit_repo: AuditRepository,
        account_repo: AccountRepository,
    ) -> None:
        self.session = session
        self.app_repo = app_repo
        self.env_repo = env_repo
        self.revision_repo = revision_repo
        self.audit_repo = audit_repo
        self.account_repo = account_repo

    def _guard_rotation(self) -> int:
        """Writes are refused while a key rotation is in progress (spec L.2).

        Returns the account's current key generation — new blobs are stamped
        with it (they are encrypted with the client's current AK).
        """
        account = self.account_repo.get_account()
        if account is None:
            return 1
        if account.rotation_new_gen is not None:
            raise RotationInProgressError()
        return account.current_key_gen

    def _resolve_env(
        self, account_id: str, app_name: str, env_name: str
    ) -> tuple[App, Environment]:
        app = self.app_repo.get_by_account_and_name(account_id, app_name)
        if app is None:
            raise AppOrEnvNotFoundError()
        env = self.env_repo.get_by_app_and_name(app.id, env_name)
        if env is None:
            raise AppOrEnvNotFoundError()
        return app, env

    def push(
        self,
        device: Device,
        app_name: str,
        env_name: str,
        *,
        blob: str,
        content_hash: str | None,
        parent_rev: int,
    ) -> dict:
        current_gen = self._guard_rotation()
        app = self.app_repo.get_by_account_and_name(device.account_id, app_name)
        if app is None:
            raise AppOrEnvNotFoundError()
        environment = self.env_repo.get_by_app_and_name(app.id, env_name)
        if environment is None:
            raise AppOrEnvNotFoundError()

        if parent_rev != environment.latest_rev:
            raise RevisionConflictError(environment.latest_rev, parent_rev)

        now = datetime.now(timezone.utc)
        new_rev_number = environment.latest_rev + 1

        rev = Revision(
            environment_id=environment.id,
            rev_number=new_rev_number,
            blob=blob,
            content_hash=content_hash,
            parent_rev=parent_rev if parent_rev > 0 else None,
            device_id=device.id,
            created_at=now,
            key_gen=current_gen,
        )
        self.revision_repo.create(rev)

        environment.latest_rev = new_rev_number
        environment.updated_at = now
        app.updated_at = now

        self.audit_repo.log(
            AuditAction.PUSH, device.account_id, device.id,
            app_name=app_name, env_name=env_name,
            rev_number=new_rev_number, created_at=now,
        )
        self.session.commit()

        return {
            "rev_number": new_rev_number,
            "created_at": now.isoformat() + "Z",
            "device_id": device.id,
        }

    def get_revision(
        self, device: Device, app_name: str, env_name: str, rev: str
    ) -> dict:
        app, environment = self._resolve_env(device.account_id, app_name, env_name)

        if rev == "last":
            rev_number = environment.latest_rev
        else:
            try:
                rev_number = int(rev)
            except ValueError:
                raise BadRevisionError(rev)

        if rev_number == 0:
            raise RevisionNotFoundError()

        revision = self.revision_repo.get_by_env_and_number(
            environment.id, rev_number
        )
        if revision is None:
            raise RevisionNotFoundError(rev_number)

        now = datetime.now(timezone.utc)
        self.audit_repo.log(
            AuditAction.PULL, device.account_id, device.id,
            app_name=app_name, env_name=env_name,
            rev_number=rev_number, created_at=now,
        )
        self.session.commit()

        return {
            "rev_number": revision.rev_number,
            "blob": revision.blob,
            "content_hash": revision.content_hash,
            "created_at": revision.created_at.isoformat() + "Z",
            "device_id": revision.device_id,
            "parent_rev": revision.parent_rev,
            "rollback_of": revision.rollback_of,
            "key_gen": revision.key_gen,
        }

    def list_revisions(
        self, device: Device, app_name: str, env_name: str
    ) -> dict:
        _app, environment = self._resolve_env(device.account_id, app_name, env_name)
        revisions = self.revision_repo.list_by_env(environment.id)
        return {
            "revisions": [
                {
                    "rev_number": r.rev_number,
                    "content_hash": r.content_hash,
                    "created_at": r.created_at.isoformat() + "Z",
                    "device_id": r.device_id,
                    "rollback_of": r.rollback_of,
                }
                for r in revisions
            ]
        }

    def rollback(
        self, device: Device, app_name: str, env_name: str, to_rev: int
    ) -> dict:
        self._guard_rotation()
        app, environment = self._resolve_env(device.account_id, app_name, env_name)

        source = self.revision_repo.get_by_env_and_number(environment.id, to_rev)
        if source is None:
            raise RevisionNotFoundError(to_rev)

        now = datetime.now(timezone.utc)
        new_rev_number = environment.latest_rev + 1

        rev = Revision(
            environment_id=environment.id,
            rev_number=new_rev_number,
            blob=source.blob,
            content_hash=source.content_hash,
            parent_rev=environment.latest_rev,
            device_id=device.id,
            rollback_of=to_rev,
            created_at=now,
            key_gen=source.key_gen,
        )
        self.revision_repo.create(rev)

        environment.latest_rev = new_rev_number
        environment.updated_at = now
        app.updated_at = now

        self.audit_repo.log(
            AuditAction.ROLLBACK, device.account_id, device.id,
            app_name=app_name, env_name=env_name,
            rev_number=new_rev_number, created_at=now,
        )
        self.session.commit()

        return {
            "rev_number": new_rev_number,
            "copied_from": to_rev,
        }


def get_revision_service(
    session: Annotated[Session, Depends(get_session)],
    app_repo: Annotated[AppRepository, Depends(get_app_repository)],
    env_repo: Annotated[EnvironmentRepository, Depends(get_environment_repository)],
    revision_repo: Annotated[RevisionRepository, Depends(get_revision_repository)],
    audit_repo: Annotated[AuditRepository, Depends(get_audit_repository)],
    account_repo: Annotated[AccountRepository, Depends(get_account_repository)],
) -> RevisionService:
    return RevisionService(
        session, app_repo, env_repo, revision_repo, audit_repo, account_repo
    )
