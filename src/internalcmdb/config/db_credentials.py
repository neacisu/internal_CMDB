"""PostgreSQL credential provider backed by OpenBao database static roles.

Reads the application database password from ``database/static-creds/internalcmdb``
via :class:`~internalcmdb.config.secrets.SecretProvider`, caches it briefly (~60 s),
and re-fetches automatically after authentication failures.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING
from urllib.parse import quote_plus

from internalcmdb.config.secrets import SecretProvider

if TYPE_CHECKING:
    from internalcmdb.api.config import Settings

logger = logging.getLogger(__name__)

_CACHE_TTL = 60


class PostgresCredentialsProvider:
    """Fetch and cache PostgreSQL credentials from OpenBao static roles."""

    def __init__(
        self,
        provider: SecretProvider | None = None,
        *,
        cache_ttl: int = _CACHE_TTL,
    ) -> None:
        self._provider = provider or SecretProvider()
        self._cache_ttl = cache_ttl
        self._password: str = ""
        self._username: str = ""
        self._cache_ts: float = 0.0
        self._lock = asyncio.Lock()

    def _cache_valid(self) -> bool:
        return bool(self._password) and (time.monotonic() - self._cache_ts) < self._cache_ttl

    def invalidate_cache(self) -> None:
        """Drop cached credentials and invalidate the underlying secret provider."""
        self._password = ""
        self._username = ""
        self._cache_ts = 0.0
        self._provider.invalidate_cache()

    async def get_password(self) -> str:
        """Return the current PostgreSQL password (async)."""
        if self._cache_valid():
            return self._password

        async with self._lock:
            if self._cache_valid():
                return self._password

            creds = await self._provider.get_database_static_creds()
            self._password = creds.password
            self._username = creds.username
            self._cache_ts = time.monotonic()
            return self._password

    def get_password_sync(self) -> str:
        """Return the current PostgreSQL password (sync)."""
        if self._cache_valid():
            return self._password

        creds = self._provider.get_database_static_creds_sync()
        self._password = creds.password
        self._username = creds.username
        self._cache_ts = time.monotonic()
        return self._password

    async def get_username(self) -> str:
        """Return the PostgreSQL username from static creds."""
        if self._cache_valid() and self._username:
            return self._username
        await self.get_password()
        return self._username or "internalcmdb"

    def get_username_sync(self) -> str:
        """Sync variant of :meth:`get_username`."""
        if self._cache_valid() and self._username:
            return self._username
        self.get_password_sync()
        return self._username or "internalcmdb"

    async def invalidate_on_auth_failure(self) -> None:
        """Force a credential refresh after a database authentication error."""
        logger.info("PostgreSQL auth failure — refreshing static credentials")
        self._password = ""
        self._username = ""
        self._cache_ts = 0.0
        self._provider.invalidate_cache()
        await self.get_password()

    def invalidate_on_auth_failure_sync(self) -> None:
        """Sync variant of :meth:`invalidate_on_auth_failure`."""
        logger.info("PostgreSQL auth failure — refreshing static credentials")
        self._password = ""
        self._username = ""
        self._cache_ts = 0.0
        self._provider.invalidate_cache()
        self.get_password_sync()


_default_provider = PostgresCredentialsProvider()


async def get_postgres_password() -> str:
    """Return the cached PostgreSQL password (async)."""
    return await _default_provider.get_password()


def get_postgres_password_sync() -> str:
    """Return the cached PostgreSQL password (sync)."""
    return _default_provider.get_password_sync()


def invalidate_cache() -> None:
    """Invalidate the module-level credentials cache."""
    _default_provider.invalidate_cache()


async def build_database_url(
    settings: Settings,
    *,
    driver: str | None = None,
) -> str:
    """Build a PostgreSQL DSN using fresh static credentials."""
    password = await get_postgres_password()
    username = await _default_provider.get_username()
    return _format_database_url(
        username=username,
        password=password,
        host=settings.postgres_host,
        port=settings.postgres_port,
        database=settings.postgres_db,
        sslmode=settings.postgres_sslmode,
        driver=driver,
    )


def build_database_url_sync(
    settings: Settings,
    *,
    driver: str | None = None,
) -> str:
    """Sync variant of :func:`build_database_url`."""
    password = get_postgres_password_sync()
    username = _default_provider.get_username_sync()
    return _format_database_url(
        username=username,
        password=password,
        host=settings.postgres_host,
        port=settings.postgres_port,
        database=settings.postgres_db,
        sslmode=settings.postgres_sslmode,
        driver=driver,
    )


def _format_database_url(
    *,
    username: str,
    password: str,
    host: str,
    port: int,
    database: str,
    sslmode: str,
    driver: str | None,
) -> str:
    driver_prefix = f"postgresql+{driver}" if driver else "postgresql+psycopg"
    safe_user = quote_plus(username)
    safe_password = quote_plus(password)
    return (
        f"{driver_prefix}://{safe_user}:{safe_password}@{host}:{port}/{database}?sslmode={sslmode}"
    )
