"""Tests for settings router helper functions and module-level constants.

Covers:
- _LLM_BACKEND_DEFAULTS completeness and type correctness
- _resolve_llm_backend: returns defaults when store has no values
- _resolve_llm_backend: returns store values when present
- _resolve_llm_backend: coerces timeout_s to int (guard against store returning float/str)
- _SK_* constant values match expected setting keys
- _MSG_CHANNEL_NOT_FOUND constant value
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest


# ---------------------------------------------------------------------------
# _LLM_BACKEND_DEFAULTS — structural assertions
# ---------------------------------------------------------------------------


def test_llm_backend_defaults_contains_all_four_backends() -> None:
    from internalcmdb.api.routers.settings import _LLM_BACKEND_DEFAULTS

    assert set(_LLM_BACKEND_DEFAULTS.keys()) == {"reasoning", "fast", "embed", "guard"}


def test_llm_backend_defaults_each_entry_is_url_modelid_timeout() -> None:
    from internalcmdb.api.routers.settings import _LLM_BACKEND_DEFAULTS

    for name, (url, model_id, timeout_s) in _LLM_BACKEND_DEFAULTS.items():
        assert isinstance(url, str) and url.startswith("http"), (
            f"Backend '{name}' default URL {url!r} must be an HTTP URL"
        )
        assert isinstance(model_id, str) and model_id, (
            f"Backend '{name}' default model_id must be a non-empty string"
        )
        assert isinstance(timeout_s, int) and timeout_s > 0, (
            f"Backend '{name}' default timeout_s must be a positive integer"
        )


def test_guard_default_url_matches_sk_guard_url_context() -> None:
    """The guard default URL is the canonical known endpoint — document it."""
    from internalcmdb.api.routers.settings import _LLM_BACKEND_DEFAULTS

    guard_url, _, _ = _LLM_BACKEND_DEFAULTS["guard"]
    assert guard_url == "http://10.0.1.115:8000"


# ---------------------------------------------------------------------------
# Setting-key constants
# ---------------------------------------------------------------------------


def test_sk_guard_url_constant() -> None:
    from internalcmdb.api.routers.settings import _SK_GUARD_URL

    assert _SK_GUARD_URL == "llm.guard.url"


def test_sk_obs_debug_constant() -> None:
    from internalcmdb.api.routers.settings import _SK_OBS_DEBUG

    assert _SK_OBS_DEBUG == "obs.debug_enabled"


def test_msg_channel_not_found_constant() -> None:
    from internalcmdb.api.routers.settings import _MSG_CHANNEL_NOT_FOUND

    assert _MSG_CHANNEL_NOT_FOUND == "Notification channel not found"


# ---------------------------------------------------------------------------
# _resolve_llm_backend
# ---------------------------------------------------------------------------


def _make_store_returning(values: dict[str, object]) -> AsyncMock:
    """Return a mock SettingsStore whose .get() resolves keys from *values*, else None."""
    store = AsyncMock()
    store.get = AsyncMock(side_effect=lambda key: values.get(key))
    return store


@pytest.mark.asyncio
async def test_resolve_llm_backend_returns_defaults_when_store_empty() -> None:
    from internalcmdb.api.routers.settings import _LLM_BACKEND_DEFAULTS, _resolve_llm_backend

    store = _make_store_returning({})
    for name in _LLM_BACKEND_DEFAULTS:
        default_url, default_mid, default_tmo = _LLM_BACKEND_DEFAULTS[name]
        cfg = await _resolve_llm_backend(store, name)
        assert cfg.url == default_url, f"{name}: expected default URL"
        assert cfg.model_id == default_mid, f"{name}: expected default model_id"
        assert cfg.timeout_s == default_tmo, f"{name}: expected default timeout_s"


@pytest.mark.asyncio
async def test_resolve_llm_backend_uses_store_values_when_present() -> None:
    from internalcmdb.api.routers.settings import _resolve_llm_backend

    store = _make_store_returning({
        "llm.reasoning.url":       "http://custom-host:9001",
        "llm.reasoning.model_id":  "custom-model",
        "llm.reasoning.timeout_s": 200,
    })
    cfg = await _resolve_llm_backend(store, "reasoning")
    assert cfg.url == "http://custom-host:9001"
    assert cfg.model_id == "custom-model"
    assert cfg.timeout_s == 200


@pytest.mark.asyncio
async def test_resolve_llm_backend_partial_override_falls_back_for_missing() -> None:
    """When only URL is in store, model_id and timeout_s must still use defaults."""
    from internalcmdb.api.routers.settings import _LLM_BACKEND_DEFAULTS, _resolve_llm_backend

    store = _make_store_returning({"llm.fast.url": "http://override:9999"})
    _, default_mid, default_tmo = _LLM_BACKEND_DEFAULTS["fast"]
    cfg = await _resolve_llm_backend(store, "fast")
    assert cfg.url == "http://override:9999"
    assert cfg.model_id == default_mid
    assert cfg.timeout_s == default_tmo


@pytest.mark.asyncio
async def test_resolve_llm_backend_coerces_timeout_s_to_int() -> None:
    """Store may return numeric values as float; timeout_s must always be int."""
    from internalcmdb.api.routers.settings import _resolve_llm_backend

    store = _make_store_returning({
        "llm.embed.url":       "http://embed:9003",
        "llm.embed.model_id":  "embed-model",
        "llm.embed.timeout_s": 45.7,  # float from DB
    })
    cfg = await _resolve_llm_backend(store, "embed")
    assert isinstance(cfg.timeout_s, int)
    assert cfg.timeout_s == 45


@pytest.mark.asyncio
async def test_resolve_llm_backend_guard_uses_constant_default_url() -> None:
    """Guard backend default URL must match _SK_GUARD_URL's default (_LLM_BACKEND_DEFAULTS)."""
    from internalcmdb.api.routers.settings import _LLM_BACKEND_DEFAULTS, _resolve_llm_backend

    store = _make_store_returning({})
    cfg = await _resolve_llm_backend(store, "guard")
    assert cfg.url == _LLM_BACKEND_DEFAULTS["guard"][0]
    assert cfg.model_id == _LLM_BACKEND_DEFAULTS["guard"][1]
