"""AK rotation routes (spec L / B.9)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from src.api.dependencies.auth import require_device_token, require_owner
from src.api.v1.rotation.views import PutBlobRequest, RotateBeginRequest
from src.core.services.rotation_service import RotationService, get_rotation_service
from src.models.base import Device

router = APIRouter(tags=["rotation"])


@router.post("/account/rotate/begin", dependencies=[Depends(require_owner)])
def rotate_begin(
    body: RotateBeginRequest,
    service: Annotated[RotationService, Depends(get_rotation_service)],
    device: Device = Depends(require_device_token),
) -> JSONResponse:
    return JSONResponse(status_code=200, content=service.begin(device, body))


@router.get("/account/rotate")
def rotate_status(
    service: Annotated[RotationService, Depends(get_rotation_service)],
    device: Device = Depends(require_device_token),
) -> JSONResponse:
    return JSONResponse(status_code=200, content=service.status(device))


@router.post("/account/rotate/complete", dependencies=[Depends(require_owner)])
def rotate_complete(
    service: Annotated[RotationService, Depends(get_rotation_service)],
    device: Device = Depends(require_device_token),
) -> JSONResponse:
    return JSONResponse(status_code=200, content=service.complete(device))


@router.put(
    "/apps/{name:path}/envs/{env}/revisions/{rev}/blob",
    dependencies=[Depends(require_owner)],
)
def rotate_put_blob(
    name: str,
    env: str,
    rev: int,
    body: PutBlobRequest,
    service: Annotated[RotationService, Depends(get_rotation_service)],
    device: Device = Depends(require_device_token),
) -> JSONResponse:
    return JSONResponse(
        status_code=200, content=service.put_blob(device, name, env, rev, body)
    )
