"""App and environment routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from src.api.dependencies.auth import require_device_token, require_editor, require_owner
from src.api.v1.apps.views import CreateAppRequest, CreateEnvRequest
from src.core.auth.exceptions import CopyFromUnsupportedError
from src.core.services.app_service import AppService, get_app_service
from src.models.base import Device

router = APIRouter(prefix="/apps", tags=["apps"])


@router.get("")
def apps_list(
    service: Annotated[AppService, Depends(get_app_service)],
    device: Device = Depends(require_device_token),
) -> JSONResponse:
    return JSONResponse(status_code=200, content=service.list_apps(device))


@router.post("", dependencies=[Depends(require_editor)])
def apps_create(
    body: CreateAppRequest,
    service: Annotated[AppService, Depends(get_app_service)],
    device: Device = Depends(require_device_token),
) -> JSONResponse:
    result = service.create_app(device, body.name)
    return JSONResponse(status_code=201, content=result)


@router.get("/{name:path}/envs")
def envs_list(
    name: str,
    service: Annotated[AppService, Depends(get_app_service)],
    device: Device = Depends(require_device_token),
) -> JSONResponse:
    return JSONResponse(status_code=200, content=service.list_envs(device, name))


@router.post("/{name:path}/envs", dependencies=[Depends(require_editor)])
def envs_create(
    name: str,
    body: CreateEnvRequest,
    service: Annotated[AppService, Depends(get_app_service)],
    device: Device = Depends(require_device_token),
) -> JSONResponse:
    # copy_from was removed: a server-side blob copy breaks AEAD (the blob is
    # bound to app|env|rev) — newer CLIs copy client-side. Old clients get a
    # clear error instead of an env whose every pull fails authentication.
    if body.copy_from is not None:
        raise CopyFromUnsupportedError()
    result = service.create_env(device, name, body.name)
    return JSONResponse(status_code=201, content=result)


@router.delete("/{name:path}/envs/{env}", dependencies=[Depends(require_owner)])
def envs_delete(
    name: str,
    env: str,
    service: Annotated[AppService, Depends(get_app_service)],
    device: Device = Depends(require_device_token),
) -> JSONResponse:
    result = service.delete_env(device, name, env)
    return JSONResponse(status_code=200, content=result)


@router.delete("/{name:path}", dependencies=[Depends(require_owner)])
def apps_delete(
    name: str,
    service: Annotated[AppService, Depends(get_app_service)],
    device: Device = Depends(require_device_token),
) -> JSONResponse:
    result = service.delete_app(device, name)
    return JSONResponse(status_code=200, content=result)
