"""dotMage Server -- App factory."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from src.api.v1 import health_router, v1_router
from src.core.auth.exceptions import DotMageError
from src.core.db.connection import create_db_connection, shutdown_db_connection
from src.settings import _auto_generate_bootstrap, get_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_connection(app)
    _auto_generate_bootstrap(session_factory=app.state.session_factory)
    yield
    shutdown_db_connection(app)


def create_app() -> FastAPI:
    app = FastAPI(title="dotMage Server", version="0.1.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # In production, restrict to actual admin origin
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Exception handler for domain errors
    @app.exception_handler(DotMageError)
    async def dotmage_error_handler(request, exc: DotMageError):  # noqa: ARG001
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.__class__.__name__, "message": exc.message}},
        )

    # Routers
    app.include_router(v1_router)
    app.include_router(health_router)

    # Static files (web admin)
    settings = get_settings()
    static_dir = Path(settings.STATIC_DIR)
    if static_dir.is_dir():
        app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="admin")

    return app


app = create_app()
