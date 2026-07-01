"""App and environment routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from src.api.dependencies.auth import require_device_token
from src.api.v1.apps.views import CreateAppRequest, CreateEnvRequest
from src.core.services.app_service import AppService, get_app_service
from src.models.base import Device

router = APIRouter(prefix="/apps", tags=["apps"])


@router.get("")
def apps_list(
    service: Annotated[AppService, Depends(get_app_service)],
    device: Device = Depends(require_device_token),
) -> JSONResponse:
    return JSONResponse(status_code=200, content=service.list_apps(device))


@router.post("")
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


@router.post("/{name:path}/envs")
def envs_create(
    name: str,
    body: CreateEnvRequest,
    service: Annotated[AppService, Depends(get_app_service)],
    device: Device = Depends(require_device_token),
) -> JSONResponse:
    result = service.create_env(device, name, body.name, body.copy_from)
    return JSONResponse(status_code=201, content=result)


@router.delete("/{name:path}/envs/{env}")
def envs_delete(
    name: str,
    env: str,
    service: Annotated[AppService, Depends(get_app_service)],
    device: Device = Depends(require_device_token),
) -> JSONResponse:
    result = service.delete_env(device, name, env)
    return JSONResponse(status_code=200, content=result)
