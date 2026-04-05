"""Tests for api.deps — database session factories."""
from __future__ import annotations
from unittest.mock import AsyncMock, MagicMock, patch
import pytest


def test_get_db_yields_and_closes():
    from internalcmdb.api import deps as deps_module
    mock_session = MagicMock()
    mock_factory = MagicMock(return_value=mock_session)

    with patch.object(deps_module, "_get_session_factory", return_value=mock_factory):
        gen = deps_module.get_db()
        db = next(gen)
        assert db is mock_session
        try:
            next(gen)
        except StopIteration:
            pass
    mock_session.close.assert_called_once()


def test_get_db_closes_on_exception():
    from internalcmdb.api import deps as deps_module
    mock_session = MagicMock()
    mock_factory = MagicMock(return_value=mock_session)

    with patch.object(deps_module, "_get_session_factory", return_value=mock_factory):
        gen = deps_module.get_db()
        next(gen)
        try:
            gen.throw(RuntimeError("test error"))
        except RuntimeError:
            pass
    mock_session.close.assert_called_once()


@pytest.mark.asyncio
async def test_get_async_session_yields():
    from internalcmdb.api import deps as deps_module
    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_factory = MagicMock(return_value=mock_session)

    with patch.object(deps_module, "_get_async_session_factory", return_value=mock_factory):
        gen = deps_module.get_async_session()
        session = await gen.__anext__()
        assert session is mock_session
        try:
            await gen.__anext__()
        except StopAsyncIteration:
            pass


@pytest.mark.asyncio
async def test_dispose_engines_handles_none():
    """dispose_engines should not error when engines have never been initialised."""
    from internalcmdb.api import deps as deps_module
    original_sync = deps_module._sync_engine
    original_async = deps_module._async_engine
    deps_module._sync_engine = None
    deps_module._async_engine = None
    try:
        await deps_module.dispose_engines()
    finally:
        deps_module._sync_engine = original_sync
        deps_module._async_engine = original_async


@pytest.mark.asyncio
async def test_dispose_engines_calls_dispose():
    from internalcmdb.api import deps as deps_module
    mock_sync = MagicMock()
    mock_async = AsyncMock()
    mock_async.dispose = AsyncMock()
    orig_sync = deps_module._sync_engine
    orig_async = deps_module._async_engine
    deps_module._sync_engine = mock_sync
    deps_module._async_engine = mock_async
    try:
        await deps_module.dispose_engines()
        mock_sync.dispose.assert_called_once()
        mock_async.dispose.assert_awaited_once()
    finally:
        deps_module._sync_engine = orig_sync
        deps_module._async_engine = orig_async


# ---------------------------------------------------------------------------
# _normalize_pg_url — URL normalization helper
# ---------------------------------------------------------------------------


def test_normalize_pg_url_strips_sslmode_require() -> None:
    from internalcmdb.api.deps import _normalize_pg_url

    url = "postgresql+psycopg://u:p@host:5432/db?sslmode=require"
    result = _normalize_pg_url(url)
    assert "sslmode=require" not in result
    assert "sslmode=disable" in result


def test_normalize_pg_url_switches_driver_to_asyncpg() -> None:
    from internalcmdb.api.deps import _normalize_pg_url

    url = "postgresql+psycopg://u:p@host:5432/db"
    result = _normalize_pg_url(url, driver="asyncpg")
    assert result.startswith("postgresql+asyncpg://")


def test_normalize_pg_url_overrides_host_and_port(monkeypatch) -> None:
    import pytest
    from internalcmdb.api.deps import _normalize_pg_url

    monkeypatch.setenv("POSTGRES_SYNC_HOST", "127.0.0.1")
    monkeypatch.setenv("POSTGRES_SYNC_PORT", "5433")
    url = "postgresql+psycopg://u:p@postgres.example.com:5432/db?sslmode=require"
    result = _normalize_pg_url(url)
    assert "127.0.0.1:5433" in result
    assert "postgres.example.com" not in result


def test_normalize_pg_url_preserves_credentials_and_dbname(monkeypatch) -> None:
    from internalcmdb.api.deps import _normalize_pg_url

    monkeypatch.setenv("POSTGRES_SYNC_HOST", "127.0.0.1")
    monkeypatch.setenv("POSTGRES_SYNC_PORT", "5433")
    url = "postgresql+psycopg://myuser:secret@remote:5432/mydb"
    result = _normalize_pg_url(url)
    assert "myuser:secret@" in result
    assert "/mydb" in result


def test_normalize_pg_url_no_env_keeps_original_host(monkeypatch) -> None:
    from internalcmdb.api.deps import _normalize_pg_url

    monkeypatch.delenv("POSTGRES_SYNC_HOST", raising=False)
    monkeypatch.delenv("POSTGRES_SYNC_PORT", raising=False)
    url = "postgresql+psycopg://u:p@original-host:9999/db"
    result = _normalize_pg_url(url)
    assert "original-host:9999" in result
