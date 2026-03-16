"""Application configuration — reads from .env via Pydantic Settings."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # PostgreSQL
    postgres_host: str = "localhost"
    postgres_port: int = 5433
    postgres_db: str = "internalCMDB"
    postgres_user: str = "internalcmdb"
    postgres_password: str = "change_me"
    postgres_sslmode: str = "prefer"

    # Redis / ARQ
    redis_url: str = (
        "rediss://infraq_app:aKRiMYjXij6AqCq54GQF49S-aW-sQmb4UwnbXGxAFrs@redis.infraq.app:443/0"
    )

    # Application
    log_level: str = "INFO"
    cors_origins: str = "http://localhost:3333,http://localhost:3000,http://127.0.0.1:3333"

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
            f"?sslmode={self.postgres_sslmode}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
