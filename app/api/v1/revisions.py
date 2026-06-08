"""Revision endpoints: push, pull, history, rollback."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import require_device_token
from app.db.models import App, AuditLog, Device, Environment, Revision
from app.db.session import get_db

router = APIRouter(prefix="/apps", tags=["revisions"])


class PushBody(BaseModel):
    blob: str
    content_hash: str | None = None
    parent_rev: int


class RollbackBody(BaseModel):
    to_rev: int


def _resolve_env(
    db: Session, account_id: str, app_name: str, env_name: str
) -> tuple[App | None, Environment | None]:
    app = db.execute(
        select(App).where(App.account_id == account_id, App.name == app_name)
    ).scalar_one_or_none()
    if app is None:
        return None, None
    env = db.execute(
        select(Environment).where(
            Environment.app_id == app.id, Environment.name == env_name
        )
    ).scalar_one_or_none()
    return app, env


@router.post("/{name}/envs/{env}/revisions")
def revision_push(
    name: str,
    env: str,
    body: PushBody,
    db: Session = Depends(get_db),
    device: Device = Depends(require_device_token),
) -> JSONResponse:
    app, environment = _resolve_env(db, device.account_id, name, env)
    if app is None:
        return JSONResponse(
            status_code=404,
            content={"error": {"code": "not_found", "message": f"App '{name}' not found"}},
        )
    if environment is None:
        return JSONResponse(
            status_code=404,
            content={"error": {"code": "not_found", "message": f"Environment '{env}' not found"}},
        )

    # Conflict check: parent_rev must equal current latest
    if body.parent_rev != environment.latest_rev:
        return JSONResponse(
            status_code=409,
            content={
                "error": {
                    "code": "conflict",
                    "message": f"Remote is ahead (server rev {environment.latest_rev}, your parent {body.parent_rev})",
                }
            },
        )

    now = datetime.now(timezone.utc)
    new_rev_number = environment.latest_rev + 1

    rev = Revision(
        environment_id=environment.id,
        rev_number=new_rev_number,
        blob=body.blob,
        content_hash=body.content_hash,
        parent_rev=body.parent_rev if body.parent_rev > 0 else None,
        device_id=device.id,
        created_at=now,
    )
    db.add(rev)

    environment.latest_rev = new_rev_number
    environment.updated_at = now
    app.updated_at = now

    audit = AuditLog(
        account_id=device.account_id,
        device_id=device.id,
        action="push",
        app_name=name,
        env_name=env,
        rev_number=new_rev_number,
        created_at=now,
    )
    db.add(audit)
    db.commit()

    return JSONResponse(
        status_code=201,
        content={
            "rev_number": new_rev_number,
            "created_at": now.isoformat() + "Z",
            "device_id": device.id,
        },
    )


@router.get("/{name}/envs/{env}/revisions/{rev}")
def revision_get(
    name: str,
    env: str,
    rev: str,
    db: Session = Depends(get_db),
    device: Device = Depends(require_device_token),
) -> JSONResponse:
    app, environment = _resolve_env(db, device.account_id, name, env)
    if app is None or environment is None:
        return JSONResponse(
            status_code=404,
            content={"error": {"code": "not_found", "message": "App or environment not found"}},
        )

    if rev == "last":
        rev_number = environment.latest_rev
    else:
        try:
            rev_number = int(rev)
        except ValueError:
            return JSONResponse(
                status_code=400,
                content={"error": {"code": "bad_request", "message": f"Invalid revision: {rev}"}},
            )

    if rev_number == 0:
        return JSONResponse(
            status_code=404,
            content={"error": {"code": "not_found", "message": "No revisions"}},
        )

    revision = db.execute(
        select(Revision).where(
            Revision.environment_id == environment.id,
            Revision.rev_number == rev_number,
        )
    ).scalar_one_or_none()

    if revision is None:
        return JSONResponse(
            status_code=404,
            content={"error": {"code": "not_found", "message": f"Revision {rev_number} not found"}},
        )

    # Audit pull
    now = datetime.now(timezone.utc)
    audit = AuditLog(
        account_id=device.account_id,
        device_id=device.id,
        action="pull",
        app_name=name,
        env_name=env,
        rev_number=rev_number,
        created_at=now,
    )
    db.add(audit)
    db.commit()

    return JSONResponse(
        status_code=200,
        content={
            "rev_number": revision.rev_number,
            "blob": revision.blob,
            "content_hash": revision.content_hash,
            "created_at": revision.created_at.isoformat() + "Z",
            "device_id": revision.device_id,
            "parent_rev": revision.parent_rev,
            "rollback_of": revision.rollback_of,
        },
    )


@router.get("/{name}/envs/{env}/revisions")
def revisions_list(
    name: str,
    env: str,
    db: Session = Depends(get_db),
    device: Device = Depends(require_device_token),
) -> JSONResponse:
    app, environment = _resolve_env(db, device.account_id, name, env)
    if app is None or environment is None:
        return JSONResponse(
            status_code=404,
            content={"error": {"code": "not_found", "message": "App or environment not found"}},
        )

    revisions = (
        db.execute(
            select(Revision)
            .where(Revision.environment_id == environment.id)
            .order_by(Revision.rev_number.desc())
        )
        .scalars()
        .all()
    )

    return JSONResponse(
        status_code=200,
        content={
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
        },
    )


@router.post("/{name}/envs/{env}/rollback")
def rollback(
    name: str,
    env: str,
    body: RollbackBody,
    db: Session = Depends(get_db),
    device: Device = Depends(require_device_token),
) -> JSONResponse:
    app, environment = _resolve_env(db, device.account_id, name, env)
    if app is None or environment is None:
        return JSONResponse(
            status_code=404,
            content={"error": {"code": "not_found", "message": "App or environment not found"}},
        )

    # Find the source revision
    source = db.execute(
        select(Revision).where(
            Revision.environment_id == environment.id,
            Revision.rev_number == body.to_rev,
        )
    ).scalar_one_or_none()

    if source is None:
        return JSONResponse(
            status_code=404,
            content={"error": {"code": "not_found", "message": f"Revision {body.to_rev} not found"}},
        )

    now = datetime.now(timezone.utc)
    new_rev_number = environment.latest_rev + 1

    rev = Revision(
        environment_id=environment.id,
        rev_number=new_rev_number,
        blob=source.blob,
        content_hash=source.content_hash,
        parent_rev=environment.latest_rev,
        device_id=device.id,
        rollback_of=body.to_rev,
        created_at=now,
    )
    db.add(rev)

    environment.latest_rev = new_rev_number
    environment.updated_at = now
    app.updated_at = now

    audit = AuditLog(
        account_id=device.account_id,
        device_id=device.id,
        action="rollback",
        app_name=name,
        env_name=env,
        rev_number=new_rev_number,
        created_at=now,
    )
    db.add(audit)
    db.commit()

    return JSONResponse(
        status_code=201,
        content={
            "rev_number": new_rev_number,
            "copied_from": body.to_rev,
        },
    )
