from __future__ import annotations

import dataclasses
import os
import time
from unittest.mock import MagicMock, patch

import pytest

from internalcmdb.config.secrets import (
    _VAULT_ADDR,
    _VAULT_MOUNT,
    _VAULT_PATH,
    _VAULT_TIMEOUT,
    _VAULT_TOKEN,
    SecretProvider,
    VaultConfig,
    _get_vault_client,
    _invalidate_vault_client,
    _vault_client_cache,
)


@pytest.mark.asyncio
async def test_get_returns_env_value():
    p = SecretProvider(VaultConfig(token=""))
    with patch.dict(os.environ, {"TEST_SECRET_XYZ_9999": "env-value"}):
        val = await p.get("TEST_SECRET_XYZ_9999")
    assert val == "env-value"


@pytest.mark.asyncio
async def test_get_returns_empty_when_not_found():
    p = SecretProvider(VaultConfig(token=""))
    val = await p.get("__NONEXISTENT_SECRET_ABCXYZ__")
    assert val == ""


@pytest.mark.asyncio
async def test_get_all_returns_dict():
    p = SecretProvider(VaultConfig(token=""))
    result = await p.get_all()
    assert isinstance(result, dict)
    assert "SECRET_KEY" in result


def test_cache_valid_initially_false():
    assert not SecretProvider(VaultConfig(token=""))._cache_valid()


def test_cache_valid_after_set():
    p = SecretProvider(VaultConfig(token=""), cache_ttl=60)
    p._cache = {"FOO": "bar"}
    p._cache_ts = time.monotonic()
    assert p._cache_valid()


def test_cache_invalid_after_ttl_expiry():
    p = SecretProvider(VaultConfig(token=""), cache_ttl=1)
    p._cache = {"FOO": "bar"}
    p._cache_ts = time.monotonic() - 2
    assert not p._cache_valid()


def test_vault_available_initially_false():
    assert SecretProvider(VaultConfig(token="")).vault_available is False


def test_vault_available_after_success():
    p = SecretProvider(VaultConfig(token=""))
    p._vault_available = True
    assert p.vault_available is True


def test_read_from_vault_no_token():
    p = SecretProvider(VaultConfig(token=""))
    result = p._read_from_vault("POSTGRES_PASSWORD")
    assert result is None
    assert p.vault_available is False


def test_read_from_vault_vault_unavailable_cached():
    p = SecretProvider(VaultConfig(token="token"))
    p._vault_available = False
    p._cache = {"KEY": "val"}
    p._cache_ts = time.monotonic()
    assert p._read_from_vault("KEY") is None


@pytest.mark.asyncio
async def test_vault_path_used_when_hvac_available():
    mock_client = MagicMock()
    mock_client.is_authenticated.return_value = True
    mock_client.secrets.kv.v2.read_secret_version.return_value = {
        "data": {"data": {"POSTGRES_PASSWORD": "secret123"}}  # NOSONAR python:S2068
    }
    p = SecretProvider(VaultConfig(token="fake-token"), cache_ttl=300)
    with patch("internalcmdb.config.secrets._get_vault_client", return_value=mock_client):
        val = await p.get("POSTGRES_PASSWORD")
    assert val == "secret123"
    assert p.vault_available is True


@pytest.mark.asyncio
async def test_vault_exception_falls_back_to_env():
    p = SecretProvider(VaultConfig(token="fake-token"))
    with (
        patch(
            "internalcmdb.config.secrets._get_vault_client",
            side_effect=RuntimeError("vault down"),
        ),
        patch.dict(os.environ, {"REDIS_PASSWORD": "env-redis-pass"}),  # NOSONAR python:S2068
    ):
        val = await p.get("REDIS_PASSWORD")
    assert val == "env-redis-pass"


def test_invalidate_vault_client():
    _vault_client_cache["key"] = MagicMock()
    _invalidate_vault_client()
    assert len(_vault_client_cache) == 0


def test_get_vault_client_no_hvac():
    with patch.dict("sys.modules", {"hvac": None}):
        result = _get_vault_client("http://localhost:8200", "token")
    assert result is None


# ---------------------------------------------------------------------------
# VaultConfig dataclass tests
# ---------------------------------------------------------------------------


def test_vault_config_defaults():
    """VaultConfig() must mirror module-level VAULT_* env defaults."""
    cfg = VaultConfig()
    assert cfg.addr == _VAULT_ADDR
    assert cfg.token == _VAULT_TOKEN
    assert cfg.mount == _VAULT_MOUNT
    assert cfg.path == _VAULT_PATH
    assert cfg.timeout == _VAULT_TIMEOUT


def test_vault_config_custom_values():
    """Explicitly supplied VaultConfig fields override defaults."""
    cfg = VaultConfig(
        addr="http://vault.prod:8200",
        token="s.PROD-TOKEN",
        mount="kv",
        path="services/cmdb",
        timeout=5,
    )
    assert cfg.addr == "http://vault.prod:8200"
    assert cfg.token == "s.PROD-TOKEN"
    assert cfg.mount == "kv"
    assert cfg.path == "services/cmdb"
    assert cfg.timeout == 5


def test_secret_provider_propagates_vault_config():
    """SecretProvider must copy VaultConfig fields to internal attributes."""
    cfg = VaultConfig(
        addr="http://bao.internal:8200",
        token="tok-abc",
        mount="secret",
        path="cmdb/prod",
        timeout=30,
    )
    p = SecretProvider(cfg, cache_ttl=120)
    assert p._vault_addr == "http://bao.internal:8200"
    assert p._vault_token == "tok-abc"
    assert p._mount == "secret"
    assert p._path == "cmdb/prod"
    assert p._timeout == 30
    assert p._cache_ttl == 120


def test_secret_provider_no_args_uses_defaults():
    """SecretProvider() (no args) must produce the same state as an explicit VaultConfig()."""
    p_default = SecretProvider()
    p_explicit = SecretProvider(VaultConfig())
    assert p_default._vault_addr == p_explicit._vault_addr
    assert p_default._vault_token == p_explicit._vault_token
    assert p_default._mount == p_explicit._mount
    assert p_default._path == p_explicit._path
    assert p_default._timeout == p_explicit._timeout
    assert p_default._cache_ttl == p_explicit._cache_ttl


def test_vault_config_is_dataclass():
    """VaultConfig must be a proper dataclass (has __dataclass_fields__)."""
    assert dataclasses.is_dataclass(VaultConfig)
    fields = {f.name for f in dataclasses.fields(VaultConfig)}
    assert fields == {"addr", "token", "mount", "path", "timeout"}
