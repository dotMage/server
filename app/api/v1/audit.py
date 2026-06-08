from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("")
async def audit_list() -> JSONResponse:
    return JSONResponse(status_code=501, content={"detail": "not implemented"})
