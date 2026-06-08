from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/apps", tags=["apps"])


@router.get("")
async def apps_list() -> JSONResponse:
    return JSONResponse(status_code=501, content={"detail": "not implemented"})


@router.post("")
async def apps_create() -> JSONResponse:
    return JSONResponse(status_code=501, content={"detail": "not implemented"})


@router.get("/{name}/envs")
async def envs_list(name: str) -> JSONResponse:
    return JSONResponse(status_code=501, content={"detail": "not implemented"})


@router.post("/{name}/envs")
async def envs_create(name: str) -> JSONResponse:
    return JSONResponse(status_code=501, content={"detail": "not implemented"})


@router.delete("/{name}/envs/{env}")
async def envs_delete(name: str, env: str) -> JSONResponse:
    return JSONResponse(status_code=501, content={"detail": "not implemented"})
