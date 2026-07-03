"""Audit log business logic."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from src.core.db.repository.audit_repo import AuditRepository, get_audit_repository
from src.models.base import Device


class AuditService:
    def __init__(self, audit_repo: AuditRepository) -> None:
        self.audit_repo = audit_repo

    def list_events(
        self,
        device: Device,
        *,
        app_name: str | None = None,
        env_name: str | None = None,
        limit: int = 100,
    ) -> dict:
        events = self.audit_repo.list_for_account(
            device.account_id,
            app_name=app_name,
            env_name=env_name,
            limit=limit,
        )
        names = self.audit_repo.user_names(device.account_id)
        return {
            "events": [
                {
                    "id": e.id,
                    "device_id": e.device_id,
                    "user": names.get(e.user_id) if e.user_id else None,
                    "action": e.action,
                    "app_name": e.app_name,
                    "env_name": e.env_name,
                    "rev_number": e.rev_number,
                    "at": e.created_at.isoformat() + "Z",
                }
                for e in events
            ]
        }


def get_audit_service(
    audit_repo: Annotated[AuditRepository, Depends(get_audit_repository)],
) -> AuditService:
    return AuditService(audit_repo)
