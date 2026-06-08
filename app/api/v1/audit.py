"""Audit log endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import require_device_token
from app.db.models import AuditLog, Device
from app.db.session import get_db

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("")
def audit_list(
    limit: int = Query(default=100, le=1000),
    app: str | None = Query(default=None),
    env: str | None = Query(default=None),
    db: Session = Depends(get_db),
    device: Device = Depends(require_device_token),
) -> JSONResponse:
    query = (
        select(AuditLog)
        .where(AuditLog.account_id == device.account_id)
        .order_by(AuditLog.created_at.desc())
    )

    if app is not None:
        query = query.where(AuditLog.app_name == app)
    if env is not None:
        query = query.where(AuditLog.env_name == env)

    query = query.limit(limit)
    events = db.execute(query).scalars().all()

    return JSONResponse(
        status_code=200,
        content={
            "events": [
                {
                    "id": e.id,
                    "device_id": e.device_id,
                    "action": e.action,
                    "app_name": e.app_name,
                    "env_name": e.env_name,
                    "rev_number": e.rev_number,
                    "at": e.created_at.isoformat() + "Z",
                }
                for e in events
            ]
        },
    )
