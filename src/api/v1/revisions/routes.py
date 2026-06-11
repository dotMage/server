"""Revision routes: push, pull, history, rollback."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from src.api.dependencies.auth import check_device_scope, require_device_token
from src.api.v1.revisions.views import PushRequest, RollbackRequest
from src.core.services.revision_service import RevisionService, get_revision_service
from src.models.base import Device

router = APIRouter(prefix="/apps", tags=["revisions"])


@router.post("/{name}/envs/{env}/revisions")
def revision_push(
    name: str,
    env: str,
    body: PushRequest,
    service: Annotated[RevisionService, Depends(get_revision_service)],
    device: Device = Depends(require_device_token),
) -> JSONResponse:
    check_device_scope(device, name, env)
    result = service.push(
        device, name, env,
        blob=body.blob, content_hash=body.content_hash, parent_rev=body.parent_rev,
    )
    return JSONResponse(status_code=201, content=result)


@router.get("/{name}/envs/{env}/revisions/{rev}")
def revision_get(
    name: str,
    env: str,
    rev: str,
    service: Annotated[RevisionService, Depends(get_revision_service)],
    device: Device = Depends(require_device_token),
) -> JSONResponse:
    check_device_scope(device, name, env)
    result = service.get_revision(device, name, env, rev)
    return JSONResponse(status_code=200, content=result)


@router.get("/{name}/envs/{env}/revisions")
def revisions_list(
    name: str,
    env: str,
    service: Annotated[RevisionService, Depends(get_revision_service)],
    device: Device = Depends(require_device_token),
) -> JSONResponse:
    check_device_scope(device, name, env)
    result = service.list_revisions(device, name, env)
    return JSONResponse(status_code=200, content=result)


@router.post("/{name}/envs/{env}/rollback")
def rollback(
    name: str,
    env: str,
    body: RollbackRequest,
    service: Annotated[RevisionService, Depends(get_revision_service)],
    device: Device = Depends(require_device_token),
) -> JSONResponse:
    check_device_scope(device, name, env)
    result = service.rollback(device, name, env, body.to_rev)
    return JSONResponse(status_code=201, content=result)
