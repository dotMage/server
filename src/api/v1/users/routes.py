"""User identity + team routes (spec B.9).

`/whoami` exists in every mode; the team endpoints exist only when
DOTMAGE_MODE=team — on solo servers they 404 (attack surface equals v1).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from src.api.dependencies.auth import require_device_token
from src.api.v1.users.views import CompleteRequest, InviteRequest, RedeemRequest
from src.core.auth.exceptions import TeamModeRequiredError
from src.core.db.repository.user_repo import UserRepository, get_user_repository
from src.core.ratelimit import check_rate_limit
from src.core.services.user_service import UserService, get_user_service
from src.models.base import Device
from src.settings import Settings, get_settings

router = APIRouter(tags=["users"])


def require_team_mode(
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    if not settings.is_team:
        raise TeamModeRequiredError()


@router.get("/whoami")
def whoami(
    user_repo: Annotated[UserRepository, Depends(get_user_repository)],
    device: Device = Depends(require_device_token),
) -> JSONResponse:
    user = user_repo.get_by_id(device.user_id) if device.user_id else None
    if user is None:
        user = user_repo.owner_of(device.account_id)
    return JSONResponse(
        status_code=200,
        content={
            "user_id": user.id if user else None,
            "name": user.name if user else "owner",
            "role": user.role if user else "owner",
            "device_id": device.id,
            "device_name": device.name,
        },
    )


@router.get("/users", dependencies=[Depends(require_team_mode)])
def users_list(
    service: Annotated[UserService, Depends(get_user_service)],
    device: Device = Depends(require_device_token),
) -> JSONResponse:
    return JSONResponse(status_code=200, content=service.list_users(device))


@router.post("/users/invite", dependencies=[Depends(require_team_mode)])
def users_invite(
    body: InviteRequest,
    service: Annotated[UserService, Depends(get_user_service)],
    device: Device = Depends(require_device_token),
) -> JSONResponse:
    return JSONResponse(status_code=201, content=service.invite(device, body))


@router.post(
    "/invitations/redeem",
    dependencies=[Depends(require_team_mode), Depends(check_rate_limit)],
)
def invitations_redeem(
    body: RedeemRequest,
    service: Annotated[UserService, Depends(get_user_service)],
) -> JSONResponse:
    return JSONResponse(status_code=200, content=service.redeem(body))


@router.post(
    "/invitations/complete",
    dependencies=[Depends(require_team_mode), Depends(check_rate_limit)],
)
def invitations_complete(
    body: CompleteRequest,
    service: Annotated[UserService, Depends(get_user_service)],
) -> JSONResponse:
    return JSONResponse(status_code=201, content=service.complete(body))
