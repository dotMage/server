"""Audit action constants."""

from __future__ import annotations


class AuditAction:
    ACCOUNT_INIT = "account.init"
    ACCOUNT_KEYS_UPDATED = "account.keys_updated"
    APP_CREATED = "app.created"
    APP_DELETED = "app.deleted"
    ENV_CREATED = "env.created"
    ENV_DELETED = "env.deleted"
    PUSH = "push"
    PULL = "pull"
    ROLLBACK = "rollback"
    DEVICE_REGISTERED = "device.registered"
    DEVICE_REVOKED = "device.revoked"
    ENROLL_TOKEN_ISSUED = "enroll_token.issued"
