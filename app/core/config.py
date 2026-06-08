from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DOTMAGE_DB_URL: str = "sqlite:////data/dotmage.db"
    DOTMAGE_BOOTSTRAP_SECRET: str = ""
    DOTMAGE_TOKEN_TTL: str = "24h"
    DOTMAGE_REFRESH_TTL: str = "30d"
    DOTMAGE_RATE_LIMIT: str = "10/min"
    DOTMAGE_LOG_LEVEL: str = "info"


settings = Settings()
