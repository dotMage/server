"""User identity routes (spec B.9). Team CRUD arrives in Phase 3."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from src.api.dependencies.auth import require_device_token
from src.core.db.repository.user_repo import UserRepository, get_user_repository
from src.models.base import Device

router = APIRouter(tags=["users"])


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
