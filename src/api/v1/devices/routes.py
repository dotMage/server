"""Device management routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from src.api.dependencies.auth import require_device_token
from src.api.v1.devices.views import CiTokenRequest, EnrollTokenRequest
from src.core.services.device_service import DeviceService, get_device_service
from src.models.base import Device

router = APIRouter(prefix="/devices", tags=["devices"])


@router.get("")
def devices_list(
    service: Annotated[DeviceService, Depends(get_device_service)],
    device: Device = Depends(require_device_token),
) -> JSONResponse:
    return JSONResponse(status_code=200, content=service.list_devices(device))


@router.delete("/{device_id}")
def devices_revoke(
    device_id: str,
    service: Annotated[DeviceService, Depends(get_device_service)],
    device: Device = Depends(require_device_token),
) -> JSONResponse:
    result = service.revoke_device(device, device_id)
    return JSONResponse(status_code=200, content=result)


@router.post("/enroll-token")
def devices_enroll_token(
    body: EnrollTokenRequest,
    service: Annotated[DeviceService, Depends(get_device_service)],
    device: Device = Depends(require_device_token),
) -> JSONResponse:
    result = service.create_enroll_token(device, body.name, body.ttl, body.kind)
    return JSONResponse(status_code=201, content=result)


@router.post("/ci-token")
def devices_ci_token(
    body: CiTokenRequest,
    service: Annotated[DeviceService, Depends(get_device_service)],
    device: Device = Depends(require_device_token),
) -> JSONResponse:
    """Create a scoped CI token for a specific app+env."""
    result = service.create_ci_token(device, body.app, body.env, body.ttl)
    return JSONResponse(status_code=201, content=result)
