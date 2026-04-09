"""Tests for api.deps — database session factories."""

from __future__ import annotations

import contextlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def test_get_db_yields_and_closes():
    from internalcmdb.api import deps as deps_module  # noqa: PLC0415

    mock_session = MagicMock()
    mock_factory = MagicMock(return_value=mock_session)

    with patch.object(deps_module, "_get_session_factory", return_value=mock_factory):
        gen = deps_module.get_db()
        db = next(gen)
        assert db is mock_session
        with contextlib.suppress(StopIteration):
            next(gen)
    mock_session.close.assert_called_once()


def test_get_db_closes_on_exception():
    from internalcmdb.api import deps as deps_module  # noqa: PLC0415

    mock_session = MagicMock()
    mock_factory = MagicMock(return_value=mock_session)

    with patch.object(deps_module, "_get_session_factory", return_value=mock_factory):
        gen = deps_module.get_db()
        next(gen)
        with contextlib.suppress(RuntimeError):
            gen.throw(RuntimeError("test error"))
    mock_session.close.assert_called_once()


@pytest.mark.asyncio
async def test_get_async_session_yields():
    from internalcmdb.api import deps as deps_module  # noqa: PLC0415

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_factory = MagicMock(return_value=mock_session)

    with patch.object(deps_module, "_get_async_session_factory", return_value=mock_factory):
        gen = deps_module.get_async_session()
        session = await gen.__anext__()
        assert session is mock_session
        with contextlib.suppress(StopAsyncIteration):
            await gen.__anext__()


@pytest.mark.asyncio
async def test_dispose_engines_handles_none():
    """dispose_engines should not error when engines have never been initialised."""
    from internalcmdb.api import deps as deps_module  # noqa: PLC0415

    original_cache = dict(deps_module._engine_cache)
    deps_module._engine_cache.clear()
    try:
        await deps_module.dispose_engines()
    finally:
        deps_module._engine_cache.clear()
        deps_module._engine_cache.update(original_cache)


@pytest.mark.asyncio
async def test_dispose_engines_calls_dispose():
    from internalcmdb.api import deps as deps_module  # noqa: PLC0415

    mock_sync = MagicMock()
    mock_async = AsyncMock()
    mock_async.dispose = AsyncMock()
    orig_sync = deps_module._engine_cache.get("sync")
    orig_async = deps_module._engine_cache.get("async")
    deps_module._engine_cache["sync"] = mock_sync
    deps_module._engine_cache["async"] = mock_async
    try:
        await deps_module.dispose_engines()
        mock_sync.dispose.assert_called_once()
        mock_async.dispose.assert_awaited_once()
    finally:
        deps_module._engine_cache.pop("sync", None)
        deps_module._engine_cache.pop("async", None)
        if orig_sync is not None:
            deps_module._engine_cache["sync"] = orig_sync
        if orig_async is not None:
            deps_module._engine_cache["async"] = orig_async


# ---------------------------------------------------------------------------
# _normalize_pg_url — URL normalization helper
# ---------------------------------------------------------------------------


def test_normalize_pg_url_strips_sslmode_require() -> None:
    from internalcmdb.api.deps import _normalize_pg_url  # noqa: PLC0415

    url = "postgresql+psycopg://u:p@host:5432/db?sslmode=require"
    result = _normalize_pg_url(url)
    assert "sslmode=require" not in result
    assert "sslmode=disable" in result


def test_normalize_pg_url_switches_driver_to_asyncpg() -> None:
    from internalcmdb.api.deps import _normalize_pg_url  # noqa: PLC0415

    url = "postgresql+psycopg://u:p@host:5432/db"
    result = _normalize_pg_url(url, driver="asyncpg")
    assert result.startswith("postgresql+asyncpg://")


def test_normalize_pg_url_overrides_host_and_port(monkeypatch: pytest.MonkeyPatch) -> None:
    from internalcmdb.api.deps import _normalize_pg_url  # noqa: PLC0415

    monkeypatch.setenv("POSTGRES_SYNC_HOST", "127.0.0.1")
    monkeypatch.setenv("POSTGRES_SYNC_PORT", "5433")
    url = "postgresql+psycopg://u:p@postgres.example.com:5432/db?sslmode=require"
    result = _normalize_pg_url(url)
    assert "127.0.0.1:5433" in result
    assert "postgres.example.com" not in result


def test_normalize_pg_url_preserves_credentials_and_dbname(monkeypatch: pytest.MonkeyPatch) -> None:
    from internalcmdb.api.deps import _normalize_pg_url  # noqa: PLC0415

    monkeypatch.setenv("POSTGRES_SYNC_HOST", "127.0.0.1")
    monkeypatch.setenv("POSTGRES_SYNC_PORT", "5433")
    url = "postgresql+psycopg://myuser:secret@remote:5432/mydb"
    result = _normalize_pg_url(url)
    assert "myuser:secret@" in result
    assert "/mydb" in result


def test_normalize_pg_url_no_env_keeps_original_host(monkeypatch: pytest.MonkeyPatch) -> None:
    from internalcmdb.api.deps import _normalize_pg_url  # noqa: PLC0415

    monkeypatch.delenv("POSTGRES_SYNC_HOST", raising=False)
    monkeypatch.delenv("POSTGRES_SYNC_PORT", raising=False)
    url = "postgresql+psycopg://u:p@original-host:9999/db"
    result = _normalize_pg_url(url)
    assert "original-host:9999" in result
