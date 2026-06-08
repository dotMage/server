from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/apps", tags=["revisions"])


@router.post("/{name}/envs/{env}/revisions")
async def revision_create(name: str, env: str) -> JSONResponse:
    return JSONResponse(status_code=501, content={"detail": "not implemented"})


@router.get("/{name}/envs/{env}/revisions/{rev}")
async def revision_get(name: str, env: str, rev: str) -> JSONResponse:
    return JSONResponse(status_code=501, content={"detail": "not implemented"})


@router.get("/{name}/envs/{env}/revisions")
async def revisions_list(name: str, env: str) -> JSONResponse:
    return JSONResponse(status_code=501, content={"detail": "not implemented"})


@router.post("/{name}/envs/{env}/rollback")
async def rollback(name: str, env: str) -> JSONResponse:
    return JSONResponse(status_code=501, content={"detail": "not implemented"})
