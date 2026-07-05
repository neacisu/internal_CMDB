"""Application configuration — reads from .env via Pydantic Settings."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal
from urllib.parse import urlparse, urlunparse

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from internalcmdb.config.secrets import is_placeholder_secret, is_production_env


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

    # Redis / ARQ — real credentials MUST come from .env or VAULT, never hardcoded
    redis_url: str = "redis://localhost:6379/0"
    # When set, rewrites redis_url host/scheme for on-host redis-shared (orchestrator dev).
    redis_local_host: str = ""

    # Security
    secret_key: str = "change_me_to_a_random_32_char_or_longer_value"

    # Embedding
    embedding_vector_dim: int = 4096

    # Application
    log_level: str = "INFO"
    log_format: str = "json"  # "json" for production, "dev" for coloured console
    cors_origins: str = "http://localhost:3333,http://localhost:3000,http://127.0.0.1:3333"

    # OpenTelemetry
    otlp_endpoint: str = "http://localhost:4317"
    otlp_protocol: str = "grpc"  # "grpc" or "http"
    otlp_insecure: bool = True
    otel_sample_rate: float = 1.0  # 0.0-1.0; 1.0 = trace everything

    # Debug endpoints
    debug_enabled: bool = False

    # Auth / JWT (non-secret config only — JWT_SECRET_KEY is managed by SecretProvider)
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 120
    jwt_cookie_name: str = "cmdb_session"
    jwt_cookie_secure: bool = True
    jwt_cookie_samesite: Literal["lax", "strict", "none"] = "lax"
    jwt_cookie_httponly: bool = True

    @model_validator(mode="after")
    def apply_redis_local_host(self) -> Settings:
        """Use plain TCP to on-host redis-shared when REDIS_LOCAL_HOST is configured."""
        if not self.redis_local_host:
            return self
        parsed = urlparse(self.redis_url)
        userinfo = ""
        if parsed.username:
            userinfo = parsed.username
            if parsed.password:
                userinfo = f"{userinfo}:{parsed.password}"
            userinfo = f"{userinfo}@"
        path = parsed.path or "/0"
        self.redis_url = urlunparse(
            (
                "redis",
                f"{userinfo}{self.redis_local_host}:6379",
                path,
                "",
                "",
                "",
            )
        )
        return self

    @model_validator(mode="after")
    def reject_placeholder_secrets_in_production(self) -> Settings:
        """Fail fast when bootstrap placeholders survive into production."""
        if not is_production_env():
            return self

        if is_placeholder_secret(self.postgres_password):
            msg = "POSTGRES_PASSWORD must not use bootstrap placeholder values in production."
            raise ValueError(msg)
        if is_placeholder_secret(self.secret_key):
            msg = "SECRET_KEY must not use bootstrap placeholder values in production."
            raise ValueError(msg)
        return self

    @property
    def database_url(self) -> str:
        """Build a PostgreSQL DSN, preferring OpenBao static credentials when available."""
        try:
            from internalcmdb.config.db_credentials import build_database_url_sync  # noqa: PLC0415

            return build_database_url_sync(self)
        except Exception:
            return (
                f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
                f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
                f"?sslmode={self.postgres_sslmode}"
            )


@lru_cache
def get_settings() -> Settings:
    return Settings()
