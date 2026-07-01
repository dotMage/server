"""App & environment business logic."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from src.core.auth.exceptions import (
    AppExistsError,
    AppNotFoundError,
    EnvExistsError,
    EnvNotFoundError,
    SourceEnvNotFoundError,
)
from src.core.db.connection import get_session
from src.core.db.repository.app_repo import AppRepository, get_app_repository
from src.core.db.repository.audit_repo import AuditRepository, get_audit_repository
from src.core.db.repository.environment_repo import EnvironmentRepository, get_environment_repository
from src.core.db.repository.revision_repo import RevisionRepository, get_revision_repository
from src.enums.audit import AuditAction
from src.models.base import App, Device, Environment, Revision


class AppService:
    def __init__(
        self,
        session: Session,
        app_repo: AppRepository,
        env_repo: EnvironmentRepository,
        revision_repo: RevisionRepository,
        audit_repo: AuditRepository,
    ) -> None:
        self.session = session
        self.app_repo = app_repo
        self.env_repo = env_repo
        self.revision_repo = revision_repo
        self.audit_repo = audit_repo

    def list_apps(self, device: Device) -> dict:
        apps = self.app_repo.list_by_account(device.account_id)
        result = []
        for a in apps:
            envs = self.env_repo.list_by_app(a.id)
            result.append({
                "id": a.id,
                "name": a.name,
                "created_at": a.created_at.isoformat() + "Z",
                "updated_at": a.updated_at.isoformat() + "Z",
                "environments": [
                    {
                        "id": e.id,
                        "name": e.name,
                        "latest_rev": e.latest_rev,
                        "protected": e.protected,
                        "created_at": e.created_at.isoformat() + "Z",
                        "updated_at": e.updated_at.isoformat() + "Z",
                    }
                    for e in envs
                ],
            })
        return {"apps": result}

    def create_app(self, device: Device, name: str) -> dict:
        existing = self.app_repo.get_by_account_and_name(device.account_id, name)
        if existing is not None:
            raise AppExistsError(name)

        now = datetime.now(timezone.utc)
        app = App(
            account_id=device.account_id,
            name=name,
            created_at=now,
            updated_at=now,
        )
        self.app_repo.create(app)

        self.audit_repo.log(
            AuditAction.APP_CREATED, device.account_id, device.id,
            app_name=name, created_at=now,
        )
        self.session.commit()

        return {
            "id": app.id,
            "name": app.name,
            "created_at": app.created_at.isoformat() + "Z",
            "updated_at": app.updated_at.isoformat() + "Z",
        }

    def list_envs(self, device: Device, app_name: str) -> dict:
        app = self.app_repo.get_by_account_and_name(device.account_id, app_name)
        if app is None:
            raise AppNotFoundError(app_name)

        envs = self.env_repo.list_by_app(app.id)
        return {
            "environments": [
                {
                    "id": e.id,
                    "name": e.name,
                    "latest_rev": e.latest_rev,
                    "protected": e.protected,
                    "created_at": e.created_at.isoformat() + "Z",
                    "updated_at": e.updated_at.isoformat() + "Z",
                }
                for e in envs
            ]
        }

    def create_env(
        self, device: Device, app_name: str, env_name: str, copy_from: str | None
    ) -> dict:
        app = self.app_repo.get_by_account_and_name(device.account_id, app_name)
        if app is None:
            raise AppNotFoundError(app_name)

        existing = self.env_repo.get_by_app_and_name(app.id, env_name)
        if existing is not None:
            raise EnvExistsError(env_name)

        now = datetime.now(timezone.utc)
        env = Environment(
            app_id=app.id,
            name=env_name,
            created_at=now,
            updated_at=now,
        )
        self.env_repo.create(env)

        if copy_from:
            source_env = self.env_repo.get_by_app_and_name(app.id, copy_from)
            if source_env is None:
                raise SourceEnvNotFoundError(copy_from)

            if source_env.latest_rev > 0:
                source_rev = self.revision_repo.get_by_env_and_number(
                    source_env.id, source_env.latest_rev
                )
                if source_rev:
                    new_rev = Revision(
                        environment_id=env.id,
                        rev_number=1,
                        blob=source_rev.blob,
                        parent_rev=None,
                        device_id=device.id,
                        created_at=now,
                    )
                    self.revision_repo.create(new_rev)
                    env.latest_rev = 1

        self.audit_repo.log(
            AuditAction.ENV_CREATED, device.account_id, device.id,
            app_name=app_name, env_name=env_name, created_at=now,
        )
        self.session.commit()

        return {
            "id": env.id,
            "name": env.name,
            "latest_rev": env.latest_rev,
            "protected": env.protected,
            "created_at": env.created_at.isoformat() + "Z",
            "updated_at": env.updated_at.isoformat() + "Z",
        }

    def delete_app(self, device: Device, name: str) -> dict:
        app = self.app_repo.get_by_account_and_name(device.account_id, name)
        if app is None:
            raise AppNotFoundError(name)

        now = datetime.now(timezone.utc)
        self.audit_repo.log(
            AuditAction.APP_DELETED, device.account_id, device.id,
            app_name=name, created_at=now,
        )

        self.app_repo.delete(app)
        self.session.commit()

        return {"ok": True}

    def delete_env(self, device: Device, app_name: str, env_name: str) -> dict:
        app = self.app_repo.get_by_account_and_name(device.account_id, app_name)
        if app is None:
            raise AppNotFoundError(app_name)

        environment = self.env_repo.get_by_app_and_name(app.id, env_name)
        if environment is None:
            raise EnvNotFoundError(env_name)

        now = datetime.now(timezone.utc)
        self.audit_repo.log(
            AuditAction.ENV_DELETED, device.account_id, device.id,
            app_name=app_name, env_name=env_name, created_at=now,
        )

        self.env_repo.delete(environment)
        self.session.commit()

        return {"ok": True}


def get_app_service(
    session: Annotated[Session, Depends(get_session)],
    app_repo: Annotated[AppRepository, Depends(get_app_repository)],
    env_repo: Annotated[EnvironmentRepository, Depends(get_environment_repository)],
    revision_repo: Annotated[RevisionRepository, Depends(get_revision_repository)],
    audit_repo: Annotated[AuditRepository, Depends(get_audit_repository)],
) -> AppService:
    return AppService(session, app_repo, env_repo, revision_repo, audit_repo)
