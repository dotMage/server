from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/account", tags=["account"])


@router.post("/init")
async def account_init() -> JSONResponse:
    return JSONResponse(status_code=501, content={"detail": "not implemented"})


@router.get("/keys")
async def account_keys_get() -> JSONResponse:
    return JSONResponse(status_code=501, content={"detail": "not implemented"})


@router.patch("/keys")
async def account_keys_patch() -> JSONResponse:
    return JSONResponse(status_code=501, content={"detail": "not implemented"})
