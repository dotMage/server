"""App repository."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.db.connection import get_session
from src.models.base import App


class AppRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_account_and_name(self, account_id: str, name: str) -> App | None:
        return self.session.execute(
            select(App).where(App.account_id == account_id, App.name == name)
        ).scalar_one_or_none()

    def list_by_account(self, account_id: str) -> list[App]:
        return list(
            self.session.execute(
                select(App).where(App.account_id == account_id)
            ).scalars().all()
        )

    def create(self, app: App) -> App:
        self.session.add(app)
        self.session.flush()
        return app

    def delete(self, app: App) -> None:
        self.session.delete(app)
        self.session.flush()


def get_app_repository(
    session: Annotated[Session, Depends(get_session)],
) -> AppRepository:
    return AppRepository(session)
