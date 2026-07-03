"""Data migrations (spec E.9): solo account -> team-of-one."""

from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from src.models.base import Account, Device, User


def ensure_owner_user(session: Session) -> None:
    """If an account predates the users table, materialize user #1 (owner).

    Idempotent. Copies the account's wraps into a `users` row and points every
    existing device at it. The account row keeps its fields (old servers and
    backups still parse) but `users` becomes the source of truth.
    """
    account = session.execute(select(Account)).scalar_one_or_none()
    if account is None:
        return
    existing = (
        session.execute(
            select(User)
            .where(User.account_id == account.id)
            .order_by(User.created_at)
        )
        .scalars()
        .first()
    )
    if existing is None:
        owner = User(
            account_id=account.id,
            name="owner",
            role="owner",
            salt=account.salt,
            argon_memory=account.argon_memory,
            argon_iterations=account.argon_iterations,
            argon_parallelism=account.argon_parallelism,
            argon_version=account.argon_version,
            nonce_ak=account.nonce_ak,
            wrapped_ak=account.wrapped_ak,
            salt_rc=account.salt_rc,
            nonce_rc=account.nonce_rc,
            wrapped_ak_rc=account.wrapped_ak_rc,
            key_gen=account.current_key_gen,
            status="active",
            created_at=account.created_at,
        )
        session.add(owner)
        session.flush()
        owner_id = owner.id
    else:
        owner_id = existing.id

    session.execute(
        update(Device)
        .where(Device.account_id == account.id, Device.user_id.is_(None))
        .values(user_id=owner_id)
    )
    session.commit()
