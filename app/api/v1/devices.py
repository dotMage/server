from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/devices", tags=["devices"])


@router.get("")
async def devices_list() -> JSONResponse:
    return JSONResponse(status_code=501, content={"detail": "not implemented"})


@router.delete("/{id}")
async def devices_delete(id: str) -> JSONResponse:
    return JSONResponse(status_code=501, content={"detail": "not implemented"})


@router.post("/enroll-token")
async def devices_enroll_token() -> JSONResponse:
    return JSONResponse(status_code=501, content={"detail": "not implemented"})
