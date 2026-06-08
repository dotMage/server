from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/device")
async def auth_device() -> JSONResponse:
    return JSONResponse(status_code=501, content={"detail": "not implemented"})


@router.post("/refresh")
async def auth_refresh() -> JSONResponse:
    return JSONResponse(status_code=501, content={"detail": "not implemented"})
