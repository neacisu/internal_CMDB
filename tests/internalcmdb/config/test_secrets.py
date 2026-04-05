"""Tests for config.secrets — SecretProvider."""
from __future__ import annotations
import os
import time
from unittest.mock import MagicMock, patch
import pytest
from internalcmdb.config.secrets import SecretProvider, _get_vault_client, _invalidate_vault_client


@pytest.mark.asyncio
async def test_get_returns_env_value():
    p = SecretProvider(vault_token="")
    with patch.dict(os.environ, {"TEST_SECRET_XYZ_9999": "env-value"}):
        val = await p.get("TEST_SECRET_XYZ_9999")
    assert val == "env-value"


@pytest.mark.asyncio
async def test_get_returns_empty_when_not_found():
    p = SecretProvider(vault_token="")
    val = await p.get("__NONEXISTENT_SECRET_ABCXYZ__")
    assert val == ""


@pytest.mark.asyncio
async def test_get_all_returns_dict():
    p = SecretProvider(vault_token="")
    result = await p.get_all()
    assert isinstance(result, dict) and "SECRET_KEY" in result


def test_cache_valid_initially_false():
    assert not SecretProvider(vault_token="")._cache_valid()


def test_cache_valid_after_set():
    p = SecretProvider(vault_token="", cache_ttl=60)
    p._cache = {"FOO": "bar"}
    p._cache_ts = time.monotonic()
    assert p._cache_valid()


def test_cache_invalid_after_ttl_expiry():
    p = SecretProvider(vault_token="", cache_ttl=1)
    p._cache = {"FOO": "bar"}
    p._cache_ts = time.monotonic() - 2
    assert not p._cache_valid()


def test_vault_available_initially_false():
    assert SecretProvider(vault_token="").vault_available is False


def test_vault_available_after_success():
    p = SecretProvider(vault_token="")
    p._vault_available = True
    assert p.vault_available is True


def test_read_from_vault_no_token():
    p = SecretProvider(vault_token="")
    result = p._read_from_vault("POSTGRES_PASSWORD")
    assert result is None and p.vault_available is False


def test_read_from_vault_vault_unavailable_cached():
    p = SecretProvider(vault_token="token")
    p._vault_available = False
    p._cache = {"KEY": "val"}
    p._cache_ts = time.monotonic()
    assert p._read_from_vault("KEY") is None


@pytest.mark.asyncio
async def test_vault_path_used_when_hvac_available():
    mock_client = MagicMock()
    mock_client.is_authenticated.return_value = True
    mock_client.secrets.kv.v2.read_secret_version.return_value = {
        "data": {"data": {"POSTGRES_PASSWORD": "secret123"}}
    }
    p = SecretProvider(vault_token="fake-token", cache_ttl=300)
    with patch("internalcmdb.config.secrets._get_vault_client", return_value=mock_client):
        val = await p.get("POSTGRES_PASSWORD")
    assert val == "secret123" and p.vault_available is True


@pytest.mark.asyncio
async def test_vault_exception_falls_back_to_env():
    p = SecretProvider(vault_token="fake-token")
    with patch("internalcmdb.config.secrets._get_vault_client", side_effect=RuntimeError("vault down")):
        with patch.dict(os.environ, {"REDIS_PASSWORD": "env-redis-pass"}):
            val = await p.get("REDIS_PASSWORD")
    assert val == "env-redis-pass"


def test_invalidate_vault_client():
    from internalcmdb.config.secrets import _vault_client_cache
    _vault_client_cache["key"] = MagicMock()
    _invalidate_vault_client()
    assert len(_vault_client_cache) == 0


def test_get_vault_client_no_hvac():
    with patch.dict("sys.modules", {"hvac": None}):
        result = _get_vault_client("http://localhost:8200", "token")
    assert result is None
