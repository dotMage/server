"""User repository (spec E.9)."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.db.connection import get_session
from src.models.base import User


class UserRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_id(self, user_id: str) -> User | None:
        return self.session.get(User, user_id)

    def get_by_account_and_name(self, account_id: str, name: str) -> User | None:
        return self.session.execute(
            select(User).where(User.account_id == account_id, User.name == name)
        ).scalar_one_or_none()

    def list_by_account(self, account_id: str) -> list[User]:
        return list(
            self.session.execute(
                select(User)
                .where(User.account_id == account_id)
                .order_by(User.created_at)
            )
            .scalars()
            .all()
        )

    def owner_of(self, account_id: str) -> User | None:
        """The first active owner — target for legacy (pre-team) writes."""
        return self.session.execute(
            select(User)
            .where(
                User.account_id == account_id,
                User.role == "owner",
                User.status == "active",
            )
            .order_by(User.created_at)
        ).scalars().first()

    def create(self, user: User) -> User:
        self.session.add(user)
        self.session.flush()
        return user


def get_user_repository(
    session: Annotated[Session, Depends(get_session)],
) -> UserRepository:
    return UserRepository(session)
