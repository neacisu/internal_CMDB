"""Tests for config.settings_store — SettingsStore."""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from internalcmdb.config.settings_store import SettingsStore, _SECRET_MASK


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_row(
    key: str,
    value: Any,
    *,
    is_secret: bool = False,
    group: str = "llm",
    type_hint: str = "string",
    default: Any = None,
) -> dict[str, Any]:
    return {
        "setting_key": key,
        "setting_group": group,
        "value_jsonb": value,
        "default_jsonb": default if default is not None else value,
        "type_hint": type_hint,
        "description": f"Test setting {key}",
        "is_secret": is_secret,
        "requires_restart": False,
        "updated_at": None,
        "updated_by": None,
    }


@pytest.fixture()
def store() -> SettingsStore:
    # Patch create_engine so the fixture doesn't require a real DB driver.
    with patch("sqlalchemy.create_engine", return_value=MagicMock()):
        return SettingsStore("postgresql+psycopg://user:pass@localhost:5432/testdb", cache_ttl=60.0)


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------


def test_cache_hit_initially_none(store: SettingsStore) -> None:
    assert store._cache_hit("missing-key") is None


def test_cache_put_and_hit(store: SettingsStore) -> None:
    store._cache_put("mykey", "value123")
    assert store._cache_hit("mykey") == "value123"


def test_cache_invalidate(store: SettingsStore) -> None:
    store._cache_put("llm.url", "http://x")
    store._cache_invalidate("__row__llm.url")
    # Group cache should also be invalidated
    assert store._cache_hit("__group__llm") is None
    assert store._cache_hit("__all__") is None


def test_cache_expires() -> None:
    # Force a very short TTL store
    with patch("sqlalchemy.create_engine", return_value=MagicMock()):
        fast_store = SettingsStore("postgresql+psycopg://user:pass@localhost:5432/testdb", cache_ttl=0.01)
    fast_store._cache_put("x", "val")
    time.sleep(0.02)
    assert fast_store._cache_hit("x") is None


# ---------------------------------------------------------------------------
# mask_if_secret
# ---------------------------------------------------------------------------


def test_mask_non_secret_row(store: SettingsStore) -> None:
    row = _make_row("llm.url", "http://10.0.1.10:49001", is_secret=False)
    out = store._mask_if_secret(row)
    assert out["value_jsonb"] == "http://10.0.1.10:49001"


def test_mask_secret_row(store: SettingsStore) -> None:
    row = _make_row("llm.guard.token", "my-secret-token", is_secret=True)
    out = store._mask_if_secret(row)
    assert out["value_jsonb"] == _SECRET_MASK
    # Does not mutate original
    assert row["value_jsonb"] == "my-secret-token"


# ---------------------------------------------------------------------------
# get_row — DB fetch with cache
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_row_returns_none_for_missing(store: SettingsStore) -> None:
    with patch.object(store, "_fetch_one", return_value=None):
        row = await store.get_row("no.such.key")
    assert row is None


@pytest.mark.asyncio
async def test_get_row_returns_masked_secret(store: SettingsStore) -> None:
    secret_row = _make_row("guard.token", "actual-token", is_secret=True)
    with patch.object(store, "_fetch_one", return_value=secret_row):
        row = await store.get_row("guard.token", mask_secrets=True)
    assert row is not None
    assert row["value_jsonb"] == _SECRET_MASK


@pytest.mark.asyncio
async def test_get_row_unmasked_for_trusted(store: SettingsStore) -> None:
    secret_row = _make_row("guard.token", "actual-token", is_secret=True)
    with patch.object(store, "_fetch_one", return_value=secret_row):
        row = await store.get_row("guard.token", mask_secrets=False)
    assert row is not None
    assert row["value_jsonb"] == "actual-token"


@pytest.mark.asyncio
async def test_get_row_cached_on_second_fetch(store: SettingsStore) -> None:
    row = _make_row("llm.url", "http://x", is_secret=False)
    call_count = 0

    def _fetch(key: str) -> dict | None:
        nonlocal call_count
        call_count += 1
        return row

    with patch.object(store, "_fetch_one", side_effect=_fetch):
        await store.get_row("llm.url")
        await store.get_row("llm.url")

    # Second call served from cache
    assert call_count == 1


# ---------------------------------------------------------------------------
# get — extracts value_jsonb
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_returns_value(store: SettingsStore) -> None:
    row = _make_row("llm.timeout", 120, type_hint="integer")
    with patch.object(store, "_fetch_one", return_value=row):
        val = await store.get("llm.timeout")
    assert val == 120


@pytest.mark.asyncio
async def test_get_returns_none_for_missing(store: SettingsStore) -> None:
    with patch.object(store, "_fetch_one", return_value=None):
        val = await store.get("no.key")
    assert val is None


@pytest.mark.asyncio
async def test_get_masks_secret(store: SettingsStore) -> None:
    row = _make_row("guard.token", "real-tok", is_secret=True)
    with patch.object(store, "_fetch_one", return_value=row):
        val = await store.get("guard.token")
    assert val == _SECRET_MASK


# ---------------------------------------------------------------------------
# get_raw_secret — returns unmasked value
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_raw_secret_returns_plaintext(store: SettingsStore) -> None:
    row = _make_row("guard.token", "real-tok", is_secret=True)
    with patch.object(store, "_fetch_one", return_value=row):
        val = await store.get_raw_secret("guard.token")
    assert val == "real-tok"


@pytest.mark.asyncio
async def test_get_raw_secret_returns_none_for_missing(store: SettingsStore) -> None:
    with patch.object(store, "_fetch_one", return_value=None):
        val = await store.get_raw_secret("no.such")
    assert val is None


# ---------------------------------------------------------------------------
# set — writes and invalidates cache
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_set_updates_value_and_invalidates_cache(store: SettingsStore) -> None:
    original_row = _make_row("llm.url", "http://old")
    updated_row = _make_row("llm.url", "http://new")

    # Prime the cache
    store._cache_put("__row__llm.url", original_row)

    with patch.object(store, "_upsert_row", return_value=updated_row):
        result = await store.set("llm.url", "http://new", updated_by="test-user")

    assert result["value_jsonb"] == "http://new"
    # Cache should be cleared
    assert store._cache_hit("__row__llm.url") is None


@pytest.mark.asyncio
async def test_set_raises_key_error_for_missing_key(store: SettingsStore) -> None:
    with patch.object(store, "_upsert_row", side_effect=KeyError("missing.key")):
        with pytest.raises(KeyError):
            await store.set("missing.key", "val", updated_by="test")


# ---------------------------------------------------------------------------
# reset_to_default
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reset_to_default(store: SettingsStore) -> None:
    reset_row = _make_row("llm.timeout", 120)
    with patch.object(store, "_reset_row", return_value=reset_row):
        result = await store.reset_to_default("llm.timeout")
    assert result["value_jsonb"] == 120


@pytest.mark.asyncio
async def test_reset_to_default_passes_updated_by_to_reset_row(store: SettingsStore) -> None:
    """updated_by must be forwarded to _reset_row so the audit trail is correct."""
    reset_row = _make_row("llm.timeout", 120)
    with patch.object(store, "_reset_row", return_value=reset_row) as mock_reset:
        await store.reset_to_default("llm.timeout", updated_by="admin-user")
    mock_reset.assert_called_once_with("llm.timeout", "admin-user")


@pytest.mark.asyncio
async def test_reset_to_default_uses_system_reset_by_default(store: SettingsStore) -> None:
    """Default updated_by value must be 'system_reset' when not explicitly supplied."""
    reset_row = _make_row("llm.timeout", 120)
    with patch.object(store, "_reset_row", return_value=reset_row) as mock_reset:
        await store.reset_to_default("llm.timeout")
    mock_reset.assert_called_once_with("llm.timeout", "system_reset")


# ---------------------------------------------------------------------------
# get_group
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_group_returns_rows(store: SettingsStore) -> None:
    rows = [
        _make_row("llm.url", "http://x"),
        _make_row("llm.timeout", 60),
    ]
    with patch.object(store, "_fetch_group", return_value=rows):
        result = await store.get_group("llm")
    assert len(result) == 2


@pytest.mark.asyncio
async def test_get_group_masks_secrets(store: SettingsStore) -> None:
    rows = [
        _make_row("llm.token", "secret!", is_secret=True),
    ]
    with patch.object(store, "_fetch_group", return_value=rows):
        result = await store.get_group("llm", mask_secrets=True)
    assert result[0]["value_jsonb"] == _SECRET_MASK


# ---------------------------------------------------------------------------
# get_all_groups
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_all_groups_groups_by_setting_group(store: SettingsStore) -> None:
    rows = [
        _make_row("llm.url", "http://x", group="llm"),
        _make_row("guard.fail_closed", True, group="guard"),
    ]
    with patch.object(store, "_fetch_all", return_value=rows):
        groups = await store.get_all_groups()
    assert "llm" in groups
    assert "guard" in groups
    assert len(groups["llm"]) == 1


# ---------------------------------------------------------------------------
# invalidate_all
# ---------------------------------------------------------------------------


def test_invalidate_all_clears_cache(store: SettingsStore) -> None:
    store._cache_put("__row__llm.url", {"value": "x"})
    store._cache_put("__group__llm", [])
    store._cache_put("__all__", {})
    store.invalidate_all()
    assert not store._cache


# ---------------------------------------------------------------------------
# _build_sync_url — URL normalisation (SSL bypass + local host override)
# ---------------------------------------------------------------------------


def test_build_sync_url_strips_sslmode_require() -> None:
    from internalcmdb.config.settings_store import _build_sync_url

    url = "postgresql+psycopg://user:pass@remote.host:5432/db?sslmode=require"
    result = _build_sync_url(url)
    assert "sslmode=require" not in result
    assert "sslmode=disable" in result


def test_build_sync_url_forces_sslmode_disable_when_absent() -> None:
    from internalcmdb.config.settings_store import _build_sync_url

    url = "postgresql+psycopg://user:pass@host:5432/db"
    result = _build_sync_url(url)
    assert "sslmode=disable" in result


def test_build_sync_url_overrides_host_and_port(monkeypatch: pytest.MonkeyPatch) -> None:
    from internalcmdb.config.settings_store import _build_sync_url

    monkeypatch.setenv("POSTGRES_SYNC_HOST", "127.0.0.1")
    monkeypatch.setenv("POSTGRES_SYNC_PORT", "5433")
    url = "postgresql+psycopg://user:pass@remote.host:5432/db?sslmode=require"
    result = _build_sync_url(url)
    assert "127.0.0.1:5433" in result
    assert "remote.host" not in result
    assert "sslmode=disable" in result


def test_build_sync_url_keeps_credentials_when_overriding_host(monkeypatch: pytest.MonkeyPatch) -> None:
    from internalcmdb.config.settings_store import _build_sync_url

    monkeypatch.setenv("POSTGRES_SYNC_HOST", "127.0.0.1")
    monkeypatch.setenv("POSTGRES_SYNC_PORT", "5433")
    url = "postgresql+psycopg://myuser:mypass@postgres.example.com:5432/mydb"
    result = _build_sync_url(url)
    assert "myuser:mypass@" in result
    assert "127.0.0.1:5433" in result
    assert "/mydb" in result


def test_build_sync_url_no_env_vars_keeps_original_host(monkeypatch: pytest.MonkeyPatch) -> None:
    from internalcmdb.config.settings_store import _build_sync_url

    monkeypatch.delenv("POSTGRES_SYNC_HOST", raising=False)
    monkeypatch.delenv("POSTGRES_SYNC_PORT", raising=False)
    url = "postgresql+psycopg://user:pass@myhost:9999/db?sslmode=require"
    result = _build_sync_url(url)
    assert "myhost:9999" in result


# ---------------------------------------------------------------------------
# Graceful degradation — DB errors return safe defaults
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_row_returns_none_on_db_error(store: SettingsStore) -> None:
    from sqlalchemy.exc import OperationalError

    with patch.object(store, "_fetch_one", side_effect=OperationalError("fail", None, None)):
        result = await store.get_row("llm.url")
    assert result is None


@pytest.mark.asyncio
async def test_get_group_returns_empty_list_on_db_error(store: SettingsStore) -> None:
    from sqlalchemy.exc import OperationalError

    with patch.object(store, "_fetch_group", side_effect=OperationalError("fail", None, None)):
        result = await store.get_group("llm")
    assert result == []


@pytest.mark.asyncio
async def test_get_all_groups_returns_empty_dict_on_db_error(store: SettingsStore) -> None:
    from sqlalchemy.exc import OperationalError

    with patch.object(store, "_fetch_all", side_effect=OperationalError("fail", None, None)):
        result = await store.get_all_groups()
    assert result == {}
