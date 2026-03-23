"""internalCMDB — Secret Provider with OpenBao/Vault integration (Phase 16, F16.4).

Attempts to read secrets from an OpenBao (Vault-compatible) instance first,
then falls back to environment variables.  Gracefully degrades when OpenBao
is unavailable — secrets are cached with a configurable TTL and the Vault
client is automatically reconnected when tokens are rotated.

Usage::

    from internalcmdb.config.secrets import SecretProvider

    provider = SecretProvider()
    db_password = await provider.get("POSTGRES_PASSWORD")
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Any

logger = logging.getLogger(__name__)

_VAULT_ADDR = os.getenv("VAULT_ADDR", "http://localhost:8200")
_VAULT_TOKEN = os.getenv("VAULT_TOKEN", "")
_VAULT_MOUNT = os.getenv("VAULT_SECRET_MOUNT", "secret")
_VAULT_PATH = os.getenv("VAULT_SECRET_PATH", "internalcmdb")
_VAULT_TIMEOUT = int(os.getenv("VAULT_TIMEOUT", "10"))
_VAULT_CACHE_TTL = int(os.getenv("VAULT_CACHE_TTL", "300"))

_MANAGED_SECRETS = frozenset({
    "SECRET_KEY",
    "POSTGRES_PASSWORD",
    "REDIS_PASSWORD",
})


class SecretProvider:
    """Retrieve secrets from OpenBao/Vault with environment variable fallback.

    The provider caches retrieved secrets with a configurable TTL (default
    300 s).  If the vault is unreachable, every call falls through to
    ``os.environ``.
    """

    def __init__(
        self,
        vault_addr: str = _VAULT_ADDR,
        vault_token: str = _VAULT_TOKEN,
        mount: str = _VAULT_MOUNT,
        path: str = _VAULT_PATH,
        timeout: int = _VAULT_TIMEOUT,
        cache_ttl: int = _VAULT_CACHE_TTL,
    ) -> None:
        self._vault_addr = vault_addr
        self._vault_token = vault_token
        self._mount = mount
        self._path = path
        self._timeout = timeout
        self._cache_ttl = cache_ttl
        self._cache: dict[str, str] = {}
        self._cache_ts: float = 0.0
        self._vault_available: bool | None = None
        self._lock = asyncio.Lock()

    def _cache_valid(self) -> bool:
        return bool(self._cache) and (time.monotonic() - self._cache_ts) < self._cache_ttl

    async def get(self, key: str) -> str:
        """Return the secret value for *key*.

        Lookup order:
        1. In-memory cache (if TTL not expired)
        2. OpenBao / Vault KV-v2 store
        3. Environment variable
        4. Empty string (with warning)
        """
        if self._cache_valid() and key in self._cache:
            return self._cache[key]

        async with self._lock:
            if self._cache_valid() and key in self._cache:
                return self._cache[key]

            vault_value = self._read_from_vault(key)
            if vault_value is not None:
                return vault_value

            env_value = os.environ.get(key, "")
            if env_value:
                self._cache[key] = env_value
                return env_value

        logger.warning("Secret '%s' not found in Vault or environment", key)
        return ""

    async def get_all(self) -> dict[str, str]:
        """Retrieve all managed secrets."""
        result: dict[str, str] = {}
        for key in _MANAGED_SECRETS:
            result[key] = await self.get(key)
        return result

    def _read_from_vault(self, key: str) -> str | None:
        """Read a single key from the Vault KV-v2 store (blocking hvac I/O)."""
        if self._vault_available is False and self._cache_valid():
            return None

        if not self._vault_token:
            self._vault_available = False
            logger.debug("No VAULT_TOKEN configured — skipping Vault lookup")
            return None

        try:
            client = _get_vault_client(
                self._vault_addr, self._vault_token, timeout=self._timeout,
            )
            if client is None:
                self._vault_available = False
                return None

            response: dict[str, Any] = client.secrets.kv.v2.read_secret_version(
                path=self._path,
                mount_point=self._mount,
            )
            data: dict[str, Any] = response.get("data", {}).get("data", {})
            if not isinstance(data, dict):
                logger.warning("Vault returned unexpected format for path %s", self._path)
                self._vault_available = False
                return None

            self._vault_available = True
            self._cache = {str(k): str(v) for k, v in data.items()}
            self._cache_ts = time.monotonic()

            return str(data[key]) if key in data else None

        except Exception:
            if self._vault_available is not False:
                logger.info(
                    "OpenBao/Vault at %s unavailable — falling back to env vars",
                    self._vault_addr,
                )
            self._vault_available = False
            _invalidate_vault_client()
            return None

    @property
    def vault_available(self) -> bool:
        """Whether the Vault backend has been successfully contacted."""
        return self._vault_available is True


_vault_client_cache: dict[str, Any] = {}
_vault_client_ts: float = 0.0
_VAULT_CLIENT_TTL = 600


def _invalidate_vault_client() -> None:
    """Clear the cached vault client so the next call reconnects."""
    _vault_client_cache.clear()


def _get_vault_client(addr: str, token: str, *, timeout: int = 10) -> Any:
    """Construct or return a cached hvac client with TTL-based refresh."""
    global _vault_client_ts  # noqa: PLW0603

    cache_key = f"{addr}|{token}"
    if (
        cache_key in _vault_client_cache
        and (time.monotonic() - _vault_client_ts) < _VAULT_CLIENT_TTL
    ):
        return _vault_client_cache[cache_key]

    try:
        import hvac  # noqa: PLC0415
        from hvac.adapters import RawAdapter  # noqa: PLC0415

        session_kwargs: dict[str, Any] = {}
        try:
            import requests  # noqa: PLC0415

            sess = requests.Session()
            sess.timeout = timeout  # type: ignore[attr-defined]
            session_kwargs["session"] = sess
        except ImportError:
            pass

        client = hvac.Client(url=addr, token=token, timeout=timeout, **session_kwargs)
        if client.is_authenticated():
            logger.info("Connected to OpenBao/Vault at %s", addr)
            _vault_client_cache.clear()
            _vault_client_cache[cache_key] = client
            _vault_client_ts = time.monotonic()
            return client
        logger.warning("Vault authentication failed at %s", addr)
        return None
    except ImportError:
        logger.debug("hvac package not installed — Vault integration disabled")
        return None
    except Exception:
        logger.debug("Vault connection failed", exc_info=True)
        return None
