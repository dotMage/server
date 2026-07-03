"""v1 API router aggregation."""

from fastapi import APIRouter

from src.api.v1.account.routes import router as account_router
from src.api.v1.apps.routes import router as apps_router
from src.api.v1.audit.routes import router as audit_router
from src.api.v1.auth.routes import router as auth_router
from src.api.v1.devices.routes import router as devices_router
from src.api.v1.health.routes import router as health_router
from src.api.v1.revisions.routes import router as revisions_router
from src.api.v1.rotation.routes import router as rotation_router

v1_router = APIRouter(prefix="/api/v1")
v1_router.include_router(account_router)
v1_router.include_router(auth_router)
v1_router.include_router(apps_router)
v1_router.include_router(rotation_router)
v1_router.include_router(revisions_router)
v1_router.include_router(devices_router)
v1_router.include_router(audit_router)

# Health is at /health (no /api/v1 prefix), exported separately
health_router = health_router
