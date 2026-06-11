"""Auth routes: device registration and token refresh."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header
from fastapi.responses import JSONResponse

from src.api.v1.auth.views import (
    DeviceRegisterBootstrapRequest,
    DeviceRegisterRequest,
    RefreshRequest,
)
from src.core.ratelimit import check_rate_limit
from src.core.services.auth_service import AuthService, get_auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/device")
def auth_device(
    body: DeviceRegisterRequest,
    service: Annotated[AuthService, Depends(get_auth_service)],
    authorization: str | None = Header(None),
    _rl: None = Depends(check_rate_limit),
) -> JSONResponse:
    """Register a new device using an enrollment token."""
    result = service.register_device(authorization, body.device_name)
    return JSONResponse(status_code=201, content=result)


@router.post("/refresh")
def auth_refresh(
    body: RefreshRequest,
    service: Annotated[AuthService, Depends(get_auth_service)],
    _rl: None = Depends(check_rate_limit),
) -> JSONResponse:
    """Rotate device and refresh tokens."""
    result = service.refresh_token(body.refresh_token)
    return JSONResponse(status_code=200, content=result)


@router.post("/device-register")
def auth_device_register_bootstrap(
    body: DeviceRegisterBootstrapRequest,
    service: Annotated[AuthService, Depends(get_auth_service)],
    _rl: None = Depends(check_rate_limit),
) -> JSONResponse:
    """Register a new device using the bootstrap secret."""
    result = service.register_device_with_bootstrap(
        body.bootstrap_secret, body.device_name,
    )
    return JSONResponse(status_code=201, content=result)
