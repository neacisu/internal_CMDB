"""FastAPI dependencies — database session and settings."""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator, Generator
from functools import lru_cache
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, sessionmaker

from .config import Settings, get_settings


# ---------------------------------------------------------------------------
# URL normalisation
# ---------------------------------------------------------------------------


def _normalize_pg_url(url: str, *, driver: str | None = None) -> str:
    """Return a copy of *url* safe for direct server-side use.

    1. Optionally swaps the driver prefix (e.g. ``psycopg`` → ``asyncpg``).
    2. Replaces host/port with ``POSTGRES_SYNC_HOST``/``POSTGRES_SYNC_PORT``
       when those env vars are set (bypasses Traefik TCP/SNI which requires TLS).
    3. Forces ``sslmode=disable`` — SSL at the DB level is unnecessary on this
       host; TLS for external clients is handled by the Traefik proxy layer.
    """
    if driver:
        url = url.replace("postgresql+psycopg", f"postgresql+{driver}", 1)

    parts = urlsplit(url)
    params = parse_qs(parts.query, keep_blank_values=True)
    params.pop("sslmode", None)
    params["sslmode"] = ["disable"]

    sync_host = os.environ.get("POSTGRES_SYNC_HOST", "").strip()
    sync_port = os.environ.get("POSTGRES_SYNC_PORT", "").strip()
    netloc = parts.netloc
    if sync_host or sync_port:
        at = netloc.rfind("@")
        userinfo = netloc[: at + 1] if at != -1 else ""
        hostport = netloc[at + 1 :]
        host_only = hostport.rsplit(":", 1)[0] if ":" in hostport else hostport
        new_host = sync_host if sync_host else host_only
        existing_port = hostport.rsplit(":", 1)[1] if ":" in hostport else "5432"
        new_port = sync_port if sync_port else existing_port
        netloc = f"{userinfo}{new_host}:{new_port}"

    return urlunsplit(parts._replace(netloc=netloc, query=urlencode(params, doseq=True)))


# ---------------------------------------------------------------------------
# Sync engine (used by loaders and background tasks)
# ---------------------------------------------------------------------------


_sync_engine = None
_async_engine = None


def _make_sessionmaker(settings: Settings) -> sessionmaker[Session]:
    global _sync_engine  # noqa: PLW0603
    _sync_engine = create_engine(
        _normalize_pg_url(settings.database_url),
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
    )
    return sessionmaker(bind=_sync_engine, autoflush=False, autocommit=False)


@lru_cache(maxsize=1)
def _get_session_factory() -> sessionmaker[Session]:
    """Return the module-level session factory, creating it once on first call."""
    return _make_sessionmaker(get_settings())


def get_db() -> Generator[Session]:
    """Yield a SQLAlchemy session; close on exit."""
    factory = _get_session_factory()
    db: Session = factory()
    try:
        yield db
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Async engine (used by FastAPI request handlers via asyncpg)
# ---------------------------------------------------------------------------


def _make_async_sessionmaker(settings: Settings) -> async_sessionmaker[AsyncSession]:
    global _async_engine  # noqa: PLW0603
    _async_engine = create_async_engine(
        _normalize_pg_url(settings.database_url, driver="asyncpg"),
        pool_pre_ping=True,
        pool_size=20,
        max_overflow=30,
    )
    return async_sessionmaker(bind=_async_engine, autoflush=False, expire_on_commit=False)


@lru_cache(maxsize=1)
def _get_async_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return the module-level async session factory, creating it once on first call."""
    return _make_async_sessionmaker(get_settings())


async def get_async_session() -> AsyncGenerator[AsyncSession]:
    """Yield an async SQLAlchemy session; close on exit."""
    factory = _get_async_session_factory()
    async with factory() as session:
        yield session


async def dispose_engines() -> None:
    """Dispose both sync and async engines — call during shutdown."""
    if _sync_engine is not None:
        _sync_engine.dispose()
    if _async_engine is not None:
        await _async_engine.dispose()
