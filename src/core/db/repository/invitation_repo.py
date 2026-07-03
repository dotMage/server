"""Invitation repository (spec E.9)."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.db.connection import get_session
from src.models.base import Invitation


class InvitationRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_id(self, invitation_id: str) -> Invitation | None:
        return self.session.get(Invitation, invitation_id)

    def list_pending(self, account_id: str) -> list[Invitation]:
        return list(
            self.session.execute(
                select(Invitation)
                .where(
                    Invitation.account_id == account_id,
                    Invitation.status.in_(["pending", "redeeming"]),
                )
                .order_by(Invitation.created_at)
            )
            .scalars()
            .all()
        )

    def create(self, invitation: Invitation) -> Invitation:
        self.session.add(invitation)
        self.session.flush()
        return invitation


def get_invitation_repository(
    session: Annotated[Session, Depends(get_session)],
) -> InvitationRepository:
    return InvitationRepository(session)
