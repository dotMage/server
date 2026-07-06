"""Application configuration parsed from environment variables."""

from __future__ import annotations

import hashlib
import re
import secrets
import string
import sys
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


def _parse_duration(value: str) -> int:
    """Parse a human duration string into seconds. E.g. '24h' -> 86400, '30d' -> 2592000."""
    m = re.fullmatch(r"(\d+)\s*([smhd])", value.strip())
    if not m:
        return int(value)
    amount = int(m.group(1))
    unit = m.group(2)
    multiplier = {"s": 1, "m": 60, "h": 3600, "d": 86400}
    return amount * multiplier[unit]


def _parse_rate_limit(value: str) -> int:
    """Parse rate limit like '10/min' -> 10."""
    parts = value.split("/")
    return int(parts[0])


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="DOTMAGE_",
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
    )

    DB_URL: str = "sqlite:////data/dotmage.db"
    BOOTSTRAP_SECRET: str = ""
    TOKEN_TTL: str = "24h"
    REFRESH_TTL: str = "30d"
    RATE_LIMIT: str = "10/min"
    LOG_LEVEL: str = "info"
    STATIC_DIR: str = "/app/static"
    # solo | team (spec B.9): team endpoints exist only in team mode.
    MODE: str = "solo"
    # Optional display name advertised in /health; clients adopt it as the
    # default server name so members don't have to `dmage server rename`.
    SERVER_NAME: str = ""

    @property
    def is_team(self) -> bool:
        return self.MODE.lower() == "team"

    @property
    def token_ttl_seconds(self) -> int:
        return _parse_duration(self.TOKEN_TTL)

    @property
    def refresh_ttl_seconds(self) -> int:
        return _parse_duration(self.REFRESH_TTL)

    @property
    def rate_limit_count(self) -> int:
        return _parse_rate_limit(self.RATE_LIMIT)

    @property
    def bootstrap_secret_hash(self) -> str:
        return hashlib.sha256(self.BOOTSTRAP_SECRET.encode()).hexdigest()


@lru_cache
def get_settings() -> Settings:
    return Settings()


def _auto_generate_bootstrap(session_factory=None) -> None:
    """Auto-generate bootstrap secret if not provided and no account exists yet."""
    settings = get_settings()
    if settings.BOOTSTRAP_SECRET:
        return

    # If DB is available, check whether an account already exists.
    # If it does, the bootstrap secret is already stored as a hash in the DB
    # and generating a new one would only confuse the user.
    if session_factory is not None:
        from sqlalchemy import select

        from src.models.base import Account

        session = session_factory()
        try:
            account = session.execute(select(Account)).scalar_one_or_none()
        finally:
            session.close()
        if account is not None:
            # Account exists — bootstrap secret is baked into the DB hash.
            # Set a placeholder so the server doesn't crash, but don't print it.
            settings.BOOTSTRAP_SECRET = "__account_exists__"
            return

    alphabet = string.ascii_letters + string.digits
    generated = "".join(secrets.choice(alphabet) for _ in range(12))
    settings.BOOTSTRAP_SECRET = generated
    print(
        f"[dotMage] Generated bootstrap secret: {generated}",
        file=sys.stderr,
    )
