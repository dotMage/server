"""dotMage Server — API backend for E2E-encrypted .env secret manager."""

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1 import account, apps, audit, auth, devices, revisions
from app.db.models import Account
from app.db.session import create_tables, get_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_tables()
    yield


app = FastAPI(title="dotMage Server", version="0.1.0", lifespan=lifespan)

# --- v1 routers ---
app.include_router(account.router, prefix="/api/v1")
app.include_router(auth.router, prefix="/api/v1")
app.include_router(apps.router, prefix="/api/v1")
app.include_router(revisions.router, prefix="/api/v1")
app.include_router(devices.router, prefix="/api/v1")
app.include_router(audit.router, prefix="/api/v1")


@app.get("/health")
def health(db: Session = Depends(get_db)) -> dict:
    acct = db.execute(select(Account)).scalar_one_or_none()
    exists = acct is not None
    return {"status": "ok", "version": "0.1.0", "account_exists": exists}
