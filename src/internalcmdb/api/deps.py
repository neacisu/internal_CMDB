"""FastAPI dependencies — database session and settings."""

from __future__ import annotations

from collections.abc import AsyncGenerator, Generator
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, sessionmaker

from .config import Settings, get_settings


# ---------------------------------------------------------------------------
# Sync engine (used by loaders and background tasks)
# ---------------------------------------------------------------------------


_sync_engine = None
_async_engine = None


def _make_sessionmaker(settings: Settings) -> sessionmaker[Session]:
    global _sync_engine  # noqa: PLW0603
    _sync_engine = create_engine(
        settings.database_url,
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
    url = settings.database_url.replace("postgresql+psycopg", "postgresql+asyncpg", 1)
    _async_engine = create_async_engine(
        url,
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
