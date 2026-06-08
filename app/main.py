from fastapi import FastAPI

from app.api.v1 import account, apps, audit, auth, devices, revisions

app = FastAPI(title="dotMage Server", version="0.1.0")

# --- v1 routers ---
app.include_router(account.router, prefix="/api/v1")
app.include_router(auth.router, prefix="/api/v1")
app.include_router(apps.router, prefix="/api/v1")
app.include_router(revisions.router, prefix="/api/v1")
app.include_router(devices.router, prefix="/api/v1")
app.include_router(audit.router, prefix="/api/v1")


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "version": "0.1.0", "account_exists": False}
