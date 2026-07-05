"""FastAPI dependencies — database session and settings."""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncGenerator, Generator
from functools import lru_cache
from typing import TYPE_CHECKING, Any
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit

from fastapi import Depends, HTTPException, status
from sqlalchemy import create_engine, event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, sessionmaker
from starlette.requests import Request

if TYPE_CHECKING:
    from internalcmdb.auth.models import User

from internalcmdb.config.db_credentials import (
    PostgresCredentialsProvider,
    build_database_url_sync,
    get_postgres_password,
    invalidate_cache as invalidate_db_credentials_cache,
)

from .config import Settings, get_settings

# ---------------------------------------------------------------------------
# URL normalisation
# ---------------------------------------------------------------------------

_credentials_provider = PostgresCredentialsProvider()


def _normalize_pg_url(
    url: str,
    *,
    driver: str | None = None,
    sslmode: str | None = None,
) -> str:
    """Return a copy of *url* safe for direct server-side use.

    1. Optionally swaps the driver prefix (e.g. ``psycopg`` → ``asyncpg``).
    2. Replaces host/port with ``POSTGRES_SYNC_HOST``/``POSTGRES_SYNC_PORT``
       when those env vars are set (bypasses Traefik TCP/SNI which requires TLS).
    3. Applies ``sslmode`` from settings (or explicit override).  For asyncpg
       the ``sslmode`` query param is translated to ``ssl=`` because asyncpg
       does not accept ``sslmode`` directly.
    """
    if driver:
        url = url.replace("postgresql+psycopg", f"postgresql+{driver}", 1)

    parts = urlsplit(url)
    params = parse_qs(parts.query, keep_blank_values=True)
    effective_sslmode = sslmode or params.get("sslmode", ["prefer"])[0]

    if driver == "asyncpg":
        params.pop("sslmode", None)
        if effective_sslmode == "disable":
            params["ssl"] = ["disable"]
        elif effective_sslmode in {"require", "verify-ca", "verify-full"}:
            params["ssl"] = ["require"]
        else:
            params["ssl"] = ["prefer"]
    else:
        params["sslmode"] = [effective_sslmode]

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


def _is_auth_failure(exc: BaseException) -> bool:
    message = str(exc).lower()
    return any(
        token in message
        for token in (
            "password authentication failed",
            "invalid authorization specification",
            "authentication failed",
        )
    )


# ---------------------------------------------------------------------------
# Sync engine (used by loaders and background tasks)
# ---------------------------------------------------------------------------


_engine_cache: dict[str, Any] = {}


def _make_sync_creator(settings: Settings):
    def _creator():
        import psycopg  # noqa: PLC0415

        password = _credentials_provider.get_password_sync()
        username = _credentials_provider.get_username_sync()
        sslmode = settings.postgres_sslmode
        conninfo = (
            f"host={settings.postgres_host} "
            f"port={settings.postgres_port} "
            f"dbname={settings.postgres_db} "
            f"user={username} "
            f"password={password} "
            f"sslmode={sslmode}"
        )
        sync_host = (os.environ.get("POSTGRES_SYNC_HOST") or "").strip()
        sync_port = (os.environ.get("POSTGRES_SYNC_PORT") or "").strip()
        if sync_host:
            conninfo = conninfo.replace(f"host={settings.postgres_host}", f"host={sync_host}", 1)
        if sync_port:
            conninfo = conninfo.replace(f"port={settings.postgres_port}", f"port={sync_port}", 1)
        return psycopg.connect(conninfo)

    return _creator


def _make_sessionmaker(settings: Settings) -> sessionmaker[Session]:
    url = _normalize_pg_url(
        build_database_url_sync(settings),
        sslmode=settings.postgres_sslmode,
    )
    engine = create_engine(
        url,
        creator=_make_sync_creator(settings),
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
    )

    @event.listens_for(engine, "handle_error")
    def _refresh_on_auth_failure(context: Any) -> None:
        if context.original_exception and _is_auth_failure(context.original_exception):
            _credentials_provider.invalidate_on_auth_failure_sync()

    _engine_cache["sync"] = engine
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


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


def _asyncpg_ssl_arg(sslmode: str) -> bool | str:
    if sslmode == "disable":
        return False
    if sslmode in {"require", "verify-ca", "verify-full"}:
        return "require"
    return "prefer"


def _make_async_sessionmaker(settings: Settings) -> async_sessionmaker[AsyncSession]:
    url = _normalize_pg_url(
        build_database_url_sync(settings, driver="asyncpg"),
        driver="asyncpg",
        sslmode=settings.postgres_sslmode,
    )

    async def _async_creator() -> Any:
        import asyncpg  # noqa: PLC0415

        password = await get_postgres_password()
        username = await _credentials_provider.get_username()
        host = settings.postgres_host
        port = settings.postgres_port
        sync_host = (os.environ.get("POSTGRES_SYNC_HOST") or "").strip()
        sync_port = (os.environ.get("POSTGRES_SYNC_PORT") or "").strip()
        if sync_host:
            host = sync_host
        if sync_port:
            port = int(sync_port)

        try:
            return await asyncpg.connect(
                host=host,
                port=port,
                user=username,
                password=password,
                database=settings.postgres_db,
                ssl=_asyncpg_ssl_arg(settings.postgres_sslmode),
            )
        except Exception as exc:
            if _is_auth_failure(exc):
                await _credentials_provider.invalidate_on_auth_failure()
                password = await get_postgres_password()
                username = await _credentials_provider.get_username()
                return await asyncpg.connect(
                    host=host,
                    port=port,
                    user=username,
                    password=password,
                    database=settings.postgres_db,
                    ssl=_asyncpg_ssl_arg(settings.postgres_sslmode),
                )
            raise

    engine = create_async_engine(
        url,
        async_creator=_async_creator,
        pool_pre_ping=True,
        pool_size=20,
        max_overflow=30,
    )
    _engine_cache["async"] = engine
    return async_sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


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


def reset_db_engine_cache() -> None:
    """Clear cached engines and credential caches (used by secret reload)."""
    invalidate_db_credentials_cache()
    _get_session_factory.cache_clear()
    _get_async_session_factory.cache_clear()
    _engine_cache.clear()


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
