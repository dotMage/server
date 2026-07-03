"""Health endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from src.core.db.repository.account_repo import AccountRepository, get_account_repository

router = APIRouter(tags=["health"])


@router.get("/health")
def health(
    account_repo: AccountRepository = Depends(get_account_repository),
) -> dict:
    acct = account_repo.get_account()
    return {
        "status": "ok",
        "version": "0.2.0",
        "account_exists": acct is not None,
        "features": ["rotation"],
    }
