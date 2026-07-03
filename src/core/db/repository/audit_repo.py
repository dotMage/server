"""Audit log repository."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.db.connection import get_session
from src.models.base import AuditLog, Device, User


class AuditRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def log(
        self,
        action: str,
        account_id: str,
        device_id: str | None = None,
        *,
        app_name: str | None = None,
        env_name: str | None = None,
        rev_number: int | None = None,
        meta: str | None = None,
        created_at: object | None = None,
        user_id: str | None = None,
    ) -> AuditLog:
        from datetime import datetime, timezone

        # Team mode (spec E.9): attribute the acting user. The device is in the
        # session identity map already (loaded by require_device_token).
        if user_id is None and device_id is not None:
            device = self.session.get(Device, device_id)
            user_id = device.user_id if device is not None else None

        entry = AuditLog(
            account_id=account_id,
            device_id=device_id,
            action=action,
            app_name=app_name,
            env_name=env_name,
            rev_number=rev_number,
            meta=meta,
            created_at=created_at or datetime.now(timezone.utc),
            user_id=user_id,
        )
        self.session.add(entry)
        self.session.flush()
        return entry

    def list_for_account(
        self,
        account_id: str,
        *,
        app_name: str | None = None,
        env_name: str | None = None,
        limit: int = 100,
    ) -> list[AuditLog]:
        query = (
            select(AuditLog)
            .where(AuditLog.account_id == account_id)
            .order_by(AuditLog.created_at.desc())
        )
        if app_name is not None:
            query = query.where(AuditLog.app_name == app_name)
        if env_name is not None:
            query = query.where(AuditLog.env_name == env_name)
        query = query.limit(limit)
        return list(self.session.execute(query).scalars().all())


    def user_names(self, account_id: str) -> dict[str, str]:
        rows = self.session.execute(
            select(User.id, User.name).where(User.account_id == account_id)
        ).all()
        return {uid: name for uid, name in rows}


def get_audit_repository(
    session: Annotated[Session, Depends(get_session)],
) -> AuditRepository:
    return AuditRepository(session)
