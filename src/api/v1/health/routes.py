"""Health endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from src.core.db.repository.account_repo import AccountRepository, get_account_repository
from src.settings import Settings, get_settings
from src.version import __version__

router = APIRouter(tags=["health"])


@router.get("/health")
def health(
    account_repo: AccountRepository = Depends(get_account_repository),
    settings: Settings = Depends(get_settings),
) -> dict:
    acct = account_repo.get_account()
    features = ["rotation"]
    if settings.is_team:
        features.append("team")
    body = {
        "status": "ok",
        "version": __version__,
        "account_exists": acct is not None,
        "features": features,
    }
    if settings.SERVER_NAME:
        body["server_name"] = settings.SERVER_NAME
    body["web_port"] = settings.WEB_PORT
    if settings.WEB_URL:
        body["web_url"] = settings.WEB_URL
    return body
