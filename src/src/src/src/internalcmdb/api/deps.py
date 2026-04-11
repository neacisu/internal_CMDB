"""FastAPI dependencies — database session and settings."""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncGenerator, Generator
from functools import lru_cache
from typing import TYPE_CHECKING, Any
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit

from fastapi import Depends, HTTPException, status
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, sessionmaker
from starlette.requests import Request

if TYPE_CHECKING:
    from internalcmdb.auth.models import User

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
       For asyncpg the ``sslmode`` query param is omitted (asyncpg does not
       accept it); instead ``ssl=disable`` is used.
    """
    if driver:
        url = url.replace("postgresql+psycopg", f"postgresql+{driver}", 1)

    parts = urlsplit(url)
    params = parse_qs(parts.query, keep_blank_values=True)
    params.pop("sslmode", None)

    # asyncpg does not accept the ``sslmode`` query parameter; it uses ``ssl``
    if driver == "asyncpg":
        params["ssl"] = ["disable"]
    else:
        params["sslmode"] = ["disable"]

    netloc = _rewrite_netloc(parts.netloc)
    return urlunsplit(parts._replace(netloc=netloc, query=urlencode(params, doseq=True)))


def _rewrite_netloc(netloc: str) -> str:
    """Override host/port from env vars when POSTGRES_SYNC_HOST/PORT are set."""
    sync_host = (os.environ.get("POSTGRES_SYNC_HOST") or "").strip()
    sync_port = (os.environ.get("POSTGRES_SYNC_PORT") or "").strip()
    if not sync_host and not sync_port:
        return netloc

    at = netloc.rfind("@")
    userinfo = netloc[: at + 1] if at != -1 else ""
    hostport = netloc[at + 1 :]
    host_only = hostport.rsplit(":", 1)[0] if ":" in hostport else hostport
    new_host = sync_host if sync_host else host_only
    existing_port = hostport.rsplit(":", 1)[1] if ":" in hostport else "5432"
    new_port = sync_port if sync_port else existing_port
    return f"{userinfo}{new_host}:{new_port}"


# ---------------------------------------------------------------------------
# Sync engine (used by loaders and background tasks)
# ---------------------------------------------------------------------------


_engine_cache: dict[str, Any] = {}


def _make_sessionmaker(settings: Settings) -> sessionmaker[Session]:
    _engine_cache["sync"] = create_engine(
        _normalize_pg_url(settings.database_url),
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
    )
    return sessionmaker(bind=_engine_cache["sync"], autoflush=False, autocommit=False)


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
    _engine_cache["async"] = create_async_engine(
        _normalize_pg_url(settings.database_url, driver="asyncpg"),
        pool_pre_ping=True,
        pool_size=20,
        max_overflow=30,
    )
    return async_sessionmaker(bind=_engine_cache["async"], autoflush=False, expire_on_commit=False)


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
    sync_engine = _engine_cache.get("sync")
    async_engine = _engine_cache.get("async")
    if sync_engine is not None:
        sync_engine.dispose()
    if async_engine is not None:
        await async_engine.dispose()


# ---------------------------------------------------------------------------
# Auth — current user dependency
# ---------------------------------------------------------------------------


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),  # noqa: B008
) -> User:
    """Extract and validate the JWT cookie; return the authenticated User.

    Raises HTTP 401 if the token is missing, invalid, or revoked.
    Raises HTTP 401 if the user no longer exists or is inactive.
    """
    from internalcmdb.auth.revocation import is_revoked  # noqa: PLC0415
    from internalcmdb.auth.security import decode_access_token  # noqa: PLC0415
    from internalcmdb.auth.service import AuthService  # noqa: PLC0415

    settings = get_settings()
    cookie_val: str | None = request.cookies.get(settings.jwt_cookie_name)
    if not cookie_val:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated.",
        )

    payload = decode_access_token(cookie_val)  # raises 401 on errors

    if is_revoked(payload.jti):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session has been revoked.",
        )

    svc = AuthService(db)
    user = svc.get_user_by_id(uuid.UUID(payload.sub))
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive.",
        )

    return user
