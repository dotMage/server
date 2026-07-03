"""SQLAlchemy 2.0 declarative models for dotMage."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_uuid() -> str:
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    pass


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=_new_uuid)
    salt: Mapped[str] = mapped_column(Text, nullable=False)
    argon_memory: Mapped[int] = mapped_column(Integer, nullable=False, default=65536)
    argon_iterations: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    argon_parallelism: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    argon_version: Mapped[int] = mapped_column(Integer, nullable=False, default=19)
    nonce_ak: Mapped[str] = mapped_column(Text, nullable=False)
    wrapped_ak: Mapped[str] = mapped_column(Text, nullable=False)
    salt_rc: Mapped[str | None] = mapped_column(Text, nullable=True)
    nonce_rc: Mapped[str | None] = mapped_column(Text, nullable=True)
    wrapped_ak_rc: Mapped[str | None] = mapped_column(Text, nullable=True)
    bootstrap_secret_hash: Mapped[str] = mapped_column(Text, nullable=False)
    bootstrap_used: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # AK rotation (spec L): key generation + in-progress state. The rot_* fields
    # hold the rotator's pending wraps for the new generation until `complete`.
    current_key_gen: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    rotation_new_gen: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rot_nonce_ak: Mapped[str | None] = mapped_column(Text, nullable=True)
    rot_wrapped_ak: Mapped[str | None] = mapped_column(Text, nullable=True)
    rot_salt_rc: Mapped[str | None] = mapped_column(Text, nullable=True)
    rot_nonce_rc: Mapped[str | None] = mapped_column(Text, nullable=True)
    rot_wrapped_ak_rc: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_utcnow
    )

    apps: Mapped[list[App]] = relationship(back_populates="account")
    devices: Mapped[list[Device]] = relationship(back_populates="account")
    audit_logs: Mapped[list[AuditLog]] = relationship(back_populates="account")


class App(Base):
    __tablename__ = "apps"
    __table_args__ = (UniqueConstraint("account_id", "name"),)

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=_new_uuid)
    account_id: Mapped[str] = mapped_column(
        Text, ForeignKey("accounts.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_utcnow, onupdate=_utcnow
    )

    account: Mapped[Account] = relationship(back_populates="apps")
    environments: Mapped[list[Environment]] = relationship(
        back_populates="app", cascade="all, delete-orphan"
    )


class Environment(Base):
    __tablename__ = "environments"
    __table_args__ = (UniqueConstraint("app_id", "name"),)

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=_new_uuid)
    app_id: Mapped[str] = mapped_column(
        Text, ForeignKey("apps.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    latest_rev: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    protected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_utcnow, onupdate=_utcnow
    )

    app: Mapped[App] = relationship(back_populates="environments")
    revisions: Mapped[list[Revision]] = relationship(
        back_populates="environment", cascade="all, delete-orphan"
    )


class Revision(Base):
    __tablename__ = "revisions"
    __table_args__ = (UniqueConstraint("environment_id", "rev_number"),)

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=_new_uuid)
    environment_id: Mapped[str] = mapped_column(
        Text, ForeignKey("environments.id"), nullable=False
    )
    rev_number: Mapped[int] = mapped_column(Integer, nullable=False)
    blob: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    parent_rev: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_utcnow
    )
    device_id: Mapped[str] = mapped_column(
        Text, ForeignKey("devices.id"), nullable=False
    )
    rollback_of: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # AK generation this blob is encrypted with (spec L.0).
    key_gen: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    environment: Mapped[Environment] = relationship(back_populates="revisions")
    device: Mapped[Device] = relationship(back_populates="revisions")


class Device(Base):
    __tablename__ = "devices"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=_new_uuid)
    account_id: Mapped[str] = mapped_column(
        Text, ForeignKey("accounts.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    token_hash: Mapped[str] = mapped_column(Text, nullable=False)
    refresh_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    token_expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_utcnow
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    allowed_app: Mapped[str | None] = mapped_column(Text, nullable=True)
    allowed_env: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Team mode (spec E.9): which user this device belongs to. NULL only on
    # rows written before the users migration; backfilled to user #1 (owner).
    user_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("users.id"), nullable=True
    )

    account: Mapped[Account] = relationship(back_populates="devices")
    revisions: Mapped[list[Revision]] = relationship(back_populates="device")
    audit_logs: Mapped[list[AuditLog]] = relationship(back_populates="device")


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=_new_uuid)
    account_id: Mapped[str] = mapped_column(
        Text, ForeignKey("accounts.id"), nullable=False
    )
    device_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("devices.id"), nullable=True
    )
    action: Mapped[str] = mapped_column(Text, nullable=False)
    app_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    env_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    rev_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_utcnow
    )
    meta: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Team mode (spec E.9): acting user, when known.
    user_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("users.id"), nullable=True
    )

    account: Mapped[Account] = relationship(back_populates="audit_logs")
    device: Mapped[Device | None] = relationship(back_populates="audit_logs")


class User(Base):
    """Team member (spec E.9). A migrated solo account = one owner user."""

    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("account_id", "name"),)

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=_new_uuid)
    account_id: Mapped[str] = mapped_column(
        Text, ForeignKey("accounts.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False, default="owner")
    salt: Mapped[str] = mapped_column(Text, nullable=False)
    argon_memory: Mapped[int] = mapped_column(Integer, nullable=False, default=65536)
    argon_iterations: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    argon_parallelism: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    argon_version: Mapped[int] = mapped_column(Integer, nullable=False, default=19)
    nonce_ak: Mapped[str] = mapped_column(Text, nullable=False)
    wrapped_ak: Mapped[str] = mapped_column(Text, nullable=False)
    salt_rc: Mapped[str | None] = mapped_column(Text, nullable=True)
    nonce_rc: Mapped[str | None] = mapped_column(Text, nullable=True)
    wrapped_ak_rc: Mapped[str | None] = mapped_column(Text, nullable=True)
    key_gen: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_utcnow
    )
    removed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Invitation(Base):
    """Pending team invitation with the sealed AK (spec K.1/E.9)."""

    __tablename__ = "invitations"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=_new_uuid)
    account_id: Mapped[str] = mapped_column(
        Text, ForeignKey("accounts.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False, default="editor")
    redeem_hash: Mapped[str] = mapped_column(Text, nullable=False)
    sealed_ak: Mapped[str | None] = mapped_column(Text, nullable=True)
    nonce_inv: Mapped[str | None] = mapped_column(Text, nullable=True)
    key_gen: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")
    created_by: Mapped[str | None] = mapped_column(
        Text, ForeignKey("users.id"), nullable=True
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_utcnow
    )
