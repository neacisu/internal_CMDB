"""internalCMDB — Secret Provider with OpenBao/Vault integration (Phase 16, F16.4).

Attempts to read secrets from an OpenBao (Vault-compatible) instance first,
then falls back to environment variables.  Gracefully degrades when OpenBao
is unavailable — secrets are cached with a configurable TTL and the Vault
client is automatically reconnected when tokens are rotated.

Production mode (``ENV=production``) fails hard when a managed secret is
missing or still a placeholder; development keeps the env-var fallback.

Usage::

    from internalcmdb.config.secrets import SecretProvider

    provider = SecretProvider()
    db_password = await provider.get("POSTGRES_PASSWORD")
    jwt_ring = await provider.get_jwt_secret_ring()
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

logger = logging.getLogger(__name__)

_VAULT_ADDR = os.getenv("VAULT_ADDR", "http://localhost:8200")
_VAULT_TOKEN = os.getenv("VAULT_TOKEN", "")
_VAULT_ROLE_ID = os.getenv("VAULT_ROLE_ID", "")
_VAULT_SECRET_ID_FILE = os.getenv("VAULT_SECRET_ID_FILE", "/run/secrets/bao_secret_id")
_VAULT_MOUNT = os.getenv("VAULT_SECRET_MOUNT", "secret")
_VAULT_PATH = os.getenv("VAULT_SECRET_PATH", "internalcmdb")
_VAULT_TIMEOUT = int(os.getenv("VAULT_TIMEOUT", "10"))
_VAULT_CACHE_TTL = int(os.getenv("VAULT_CACHE_TTL", "300"))
_DB_STATIC_CREDS_PATH = os.getenv("VAULT_DB_STATIC_CREDS_PATH", "internalcmdb")

_MANAGED_SECRETS = frozenset(
    {
        "SECRET_KEY",
        "POSTGRES_PASSWORD",
        "REDIS_PASSWORD",
        "JWT_SECRET_KEY",
    }
)

_PLACEHOLDER_PREFIXES = ("change_me",)
_PLACEHOLDER_EXACT = frozenset(
    {
        "change_me",
        "change_me_before_use",
        "change_me_to_a_random_32_char_or_longer_value",
        "change_me_min_32_chars_use_openbao_in_production",
    }
)


@dataclass
class VaultConfig:
    """Connection and routing configuration for the OpenBao/Vault backend.

    All fields default to the corresponding ``VAULT_*`` environment variables
    so that ``VaultConfig()`` is valid in production without any arguments.
    """

    addr: str = _VAULT_ADDR
    token: str = _VAULT_TOKEN
    role_id: str = _VAULT_ROLE_ID
    secret_id: str = ""
    secret_id_file: str = _VAULT_SECRET_ID_FILE
    mount: str = _VAULT_MOUNT
    path: str = _VAULT_PATH
    timeout: int = _VAULT_TIMEOUT
    db_static_creds_path: str = _DB_STATIC_CREDS_PATH


@dataclass
class DatabaseStaticCreds:
    """Credentials returned by OpenBao database/static-creds."""

    username: str
    password: str
    ttl: int | None = None
    last_vault_rotation: str | None = None


def is_production_env() -> bool:
    """Return True when running under the production profile."""
    return os.getenv("ENV", "").strip().lower() == "production"


def is_placeholder_secret(value: str) -> bool:
    """Return True when *value* is empty or a known bootstrap placeholder."""
    if not value:
        return True
    lower = value.strip().lower()
    if lower in _PLACEHOLDER_EXACT:
        return True
    return any(lower.startswith(prefix) for prefix in _PLACEHOLDER_PREFIXES)


def _resolve_secret_id(config: VaultConfig) -> str:
    """Load AppRole secret_id from config, env, or mounted file."""
    if config.secret_id:
        return config.secret_id.strip()
    env_val = os.getenv("VAULT_SECRET_ID", "").strip()
    if env_val:
        return env_val
    secret_file = config.secret_id_file
    if secret_file and os.path.isfile(secret_file):
        try:
            return Path(secret_file).read_text(encoding="utf-8").strip()  # type: ignore[name-defined]
        except OSError:
            logger.debug("Could not read secret_id file at %s", secret_file)
    return ""


class SecretProvider:
    """Retrieve secrets from OpenBao/Vault with environment variable fallback.

    The provider caches retrieved secrets with a configurable TTL (default
    300 s).  If the vault is unreachable, every call falls through to
    ``os.environ`` unless ``ENV=production``.
    """

    def __init__(
        self,
        config: VaultConfig | None = None,
        *,
        cache_ttl: int = _VAULT_CACHE_TTL,
    ) -> None:
        cfg = config or VaultConfig()
        self._vault_addr = cfg.addr
        self._vault_token = cfg.token
        self._role_id = cfg.role_id
        self._secret_id = _resolve_secret_id(cfg)
        self._mount = cfg.mount
        self._path = cfg.path
        self._timeout = cfg.timeout
        self._db_static_creds_path = cfg.db_static_creds_path
        self._cache_ttl = cache_ttl
        self._cache: dict[str, str] = {}
        self._cache_ts: float = 0.0
        self._jwt_ring_cache: list[str] = []
        self._jwt_ring_ts: float = 0.0
        self._db_static_cache: DatabaseStaticCreds | None = None
        self._db_static_ts: float = 0.0
        self._vault_available: bool | None = None
        self._lock = asyncio.Lock()

    def _cache_valid(self) -> bool:
        return bool(self._cache) and (time.monotonic() - self._cache_ts) < self._cache_ttl

    def _jwt_ring_cache_valid(self) -> bool:
        return (
            bool(self._jwt_ring_cache) and (time.monotonic() - self._jwt_ring_ts) < self._cache_ttl
        )

    def _db_static_cache_valid(self) -> bool:
        return (
            self._db_static_cache is not None
            and (time.monotonic() - self._db_static_ts) < self._cache_ttl
        )

    def invalidate_cache(self) -> None:
        """Clear all in-memory secret caches and the cached Vault client."""
        self._cache.clear()
        self._cache_ts = 0.0
        self._jwt_ring_cache.clear()
        self._jwt_ring_ts = 0.0
        self._db_static_cache = None
        self._db_static_ts = 0.0
        self._vault_available = None
        _invalidate_vault_client()

    async def get(self, key: str) -> str:
        """Return the secret value for *key*.

        Lookup order:
        1. In-memory cache (if TTL not expired)
        2. OpenBao / Vault KV-v2 store
        3. Environment variable (dev only)
        4. Empty string (with warning) or RuntimeError in production
        """
        if self._cache_valid() and key in self._cache:
            return self._cache[key]

        async with self._lock:
            if self._cache_valid() and key in self._cache:
                return self._cache[key]

            vault_value = self._read_from_vault(key)
            if vault_value is not None:
                return vault_value

            env_value = os.environ.get(key) or ""
            if env_value:
                if is_production_env() and is_placeholder_secret(env_value):
                    raise RuntimeError(
                        f"Secret '{key}' is a placeholder in production. "
                        "Configure OpenBao or set a real value."
                    )
                self._cache[key] = env_value
                self._cache_ts = time.monotonic()
                return env_value

        if is_production_env():
            raise RuntimeError(
                f"Secret '{key}' not found in Vault or environment (production mode)."
            )

        logger.warning("Secret '%s' not found in Vault or environment", key)
        return ""

    async def get_all(self) -> dict[str, str]:
        """Retrieve all managed secrets."""
        result: dict[str, str] = {}
        for key in _MANAGED_SECRETS:
            result[key] = await self.get(key)
        return result

    async def get_jwt_secret_ring(self) -> list[str]:
        """Return ``[current, previous?]`` JWT signing keys from KV-v2 versions."""
        if self._jwt_ring_cache_valid():
            return list(self._jwt_ring_cache)

        async with self._lock:
            if self._jwt_ring_cache_valid():
                return list(self._jwt_ring_cache)

            ring = self._read_jwt_secret_ring_from_vault()
            if ring:
                self._jwt_ring_cache = ring
                self._jwt_ring_ts = time.monotonic()
                return list(ring)

            env_value = os.environ.get("JWT_SECRET_KEY") or ""
            if env_value:
                if is_production_env() and is_placeholder_secret(env_value):
                    raise RuntimeError(
                        "JWT_SECRET_KEY is a placeholder in production. "
                        "Configure OpenBao or set a real value."
                    )
                self._jwt_ring_cache = [env_value]
                self._jwt_ring_ts = time.monotonic()
                return [env_value]

        if is_production_env():
            raise RuntimeError(
                "JWT_SECRET_KEY not found in Vault or environment (production mode)."
            )

        logger.warning("JWT secret ring not found in Vault or environment")
        return []

    def get_jwt_secret_ring_sync(self) -> list[str]:
        """Synchronous wrapper around :meth:`get_jwt_secret_ring`."""
        ring = self._read_jwt_secret_ring_from_vault()
        if ring:
            self._jwt_ring_cache = ring
            self._jwt_ring_ts = time.monotonic()
            return list(ring)

        env_value = os.environ.get("JWT_SECRET_KEY") or ""
        if env_value:
            if is_production_env() and is_placeholder_secret(env_value):
                raise RuntimeError(
                    "JWT_SECRET_KEY is a placeholder in production. "
                    "Configure OpenBao or set a real value."
                )
            self._jwt_ring_cache = [env_value]
            self._jwt_ring_ts = time.monotonic()
            return [env_value]

        if is_production_env():
            raise RuntimeError(
                "JWT_SECRET_KEY not found in Vault or environment (production mode)."
            )
        return []

    async def get_database_static_creds(self) -> DatabaseStaticCreds:
        """Return PostgreSQL credentials from ``database/static-creds/*``."""
        if self._db_static_cache_valid() and self._db_static_cache is not None:
            return self._db_static_cache

        async with self._lock:
            if self._db_static_cache_valid() and self._db_static_cache is not None:
                return self._db_static_cache

            creds = self._read_database_static_creds()
            if creds is not None:
                self._db_static_cache = creds
                self._db_static_ts = time.monotonic()
                return creds

            username = os.environ.get("POSTGRES_USER", "internalcmdb")
            password = os.environ.get("POSTGRES_PASSWORD", "")
            if password:
                if is_production_env() and is_placeholder_secret(password):
                    raise RuntimeError(
                        "POSTGRES_PASSWORD is a placeholder in production. "
                        "Configure OpenBao database static creds."
                    )
                creds = DatabaseStaticCreds(username=username, password=password)
                self._db_static_cache = creds
                self._db_static_ts = time.monotonic()
                return creds

        if is_production_env():
            raise RuntimeError(
                "Database static credentials not found in Vault or environment (production mode)."
            )

        logger.warning("Database static credentials not found in Vault or environment")
        return DatabaseStaticCreds(username="internalcmdb", password="")

    def get_database_static_creds_sync(self) -> DatabaseStaticCreds:
        """Synchronous variant of :meth:`get_database_static_creds`."""
        if self._db_static_cache_valid() and self._db_static_cache is not None:
            return self._db_static_cache

        creds = self._read_database_static_creds()
        if creds is not None:
            self._db_static_cache = creds
            self._db_static_ts = time.monotonic()
            return creds

        username = os.environ.get("POSTGRES_USER", "internalcmdb")
        password = os.environ.get("POSTGRES_PASSWORD", "")
        if password:
            if is_production_env() and is_placeholder_secret(password):
                raise RuntimeError(
                    "POSTGRES_PASSWORD is a placeholder in production. "
                    "Configure OpenBao database static creds."
                )
            creds = DatabaseStaticCreds(username=username, password=password)
            self._db_static_cache = creds
            self._db_static_ts = time.monotonic()
            return creds

        if is_production_env():
            raise RuntimeError(
                "Database static credentials not found in Vault or environment (production mode)."
            )
        return DatabaseStaticCreds(username="internalcmdb", password="")

    def _read_jwt_secret_ring_from_vault(self) -> list[str]:
        client = self._ensure_vault_client()
        if client is None:
            return []

        try:
            metadata_resp: dict[str, Any] = client.secrets.kv.v2.read_secret_metadata(
                path=self._path,
                mount_point=self._mount,
            )
            versions: dict[str, Any] = metadata_resp.get("data", {}).get("versions", {})
            if not isinstance(versions, dict) or not versions:
                return self._jwt_ring_from_single_read(client)

            version_numbers = sorted(
                (int(v) for v in versions if str(v).isdigit()),
                reverse=True,
            )
            if not version_numbers:
                return self._jwt_ring_from_single_read(client)

            ring: list[str] = []
            for version in version_numbers[:2]:
                response: dict[str, Any] = client.secrets.kv.v2.read_secret_version(
                    path=self._path,
                    mount_point=self._mount,
                    version=version,
                )
                data: Any = response.get("data", {}).get("data", {})
                if isinstance(data, dict):
                    secret = str(data.get("JWT_SECRET_KEY", ""))
                    if secret and secret not in ring:
                        ring.append(secret)

            if ring:
                self._vault_available = True
            return ring
        except Exception:
            logger.debug("Failed to read JWT secret ring from Vault", exc_info=True)
            self._vault_available = False
            _invalidate_vault_client()
            return []

    def _jwt_ring_from_single_read(self, client: Any) -> list[str]:
        response: dict[str, Any] = client.secrets.kv.v2.read_secret_version(
            path=self._path,
            mount_point=self._mount,
        )
        data: Any = response.get("data", {}).get("data", {})
        if not isinstance(data, dict):
            return []
        secret = str(data.get("JWT_SECRET_KEY", ""))
        if secret:
            self._vault_available = True
            return [secret]
        return []

    def _read_database_static_creds(self) -> DatabaseStaticCreds | None:
        client = self._ensure_vault_client()
        if client is None:
            return None

        try:
            response: dict[str, Any] = client.secrets.database.generate_static_credentials(
                name=self._db_static_creds_path,
            )
            data: Any = response.get("data", {})
            if not isinstance(data, dict):
                return None
            username = str(data.get("username", ""))
            password = str(data.get("password", ""))
            if not username or not password:
                return None
            self._vault_available = True
            return DatabaseStaticCreds(
                username=username,
                password=password,
                ttl=int(data["ttl"]) if data.get("ttl") is not None else None,
                last_vault_rotation=str(data.get("last_vault_rotation") or "") or None,
            )
        except Exception:
            logger.debug("Failed to read database static credentials from Vault", exc_info=True)
            self._vault_available = False
            _invalidate_vault_client()
            return None

    def _read_from_vault(self, key: str) -> str | None:
        """Read a single key from the Vault KV-v2 store (blocking hvac I/O)."""
        if self._vault_available is False and self._cache_valid():
            return None

        try:
            client = self._ensure_vault_client()
            if client is None:
                return None

            response: dict[str, Any] = client.secrets.kv.v2.read_secret_version(
                path=self._path,
                mount_point=self._mount,
            )
            data: Any = response.get("data", {}).get("data", {})
            if not isinstance(data, dict):
                logger.warning("Vault returned unexpected format for path %s", self._path)
                self._vault_available = False
                return None

            vault_data = cast("dict[str, Any]", data)
            self._vault_available = True
            self._cache = {str(k): str(v) for k, v in vault_data.items()}
            self._cache_ts = time.monotonic()

            return str(vault_data[key]) if key in vault_data else None

        except Exception:
            if self._vault_available is not False:
                logger.info(
                    "OpenBao/Vault at %s unavailable — falling back to env vars",
                    self._vault_addr,
                )
            self._vault_available = False
            _invalidate_vault_client()
            return None

    def _ensure_vault_client(self) -> Any:
        token = self._resolve_vault_token()
        if not token:
            self._vault_available = False
            logger.debug("No Vault token or AppRole credentials configured")
            return None
        return _get_vault_client(
            self._vault_addr,
            token,
            timeout=self._timeout,
        )

    def _resolve_vault_token(self) -> str:
        if self._vault_token:
            return self._vault_token
        if not self._role_id or not self._secret_id:
            return ""
        token = _login_approle(self._vault_addr, self._role_id, self._secret_id, self._timeout)
        if token:
            self._vault_token = token
        return token

    @property
    def vault_available(self) -> bool:
        """Whether the Vault backend has been successfully contacted."""
        return self._vault_available is True


_vault_client_cache: dict[str, Any] = {}
_VAULT_CLIENT_TTL = 600


def _invalidate_vault_client() -> None:
    """Clear the cached vault client so the next call reconnects."""
    _vault_client_cache.clear()


def _login_approle(addr: str, role_id: str, secret_id: str, timeout: int) -> str:
    """Authenticate via AppRole and return a client token."""
    cache_key = f"approle|{addr}|{role_id}|{secret_id}"
    cached = _vault_client_cache.get(cache_key)
    if (
        isinstance(cached, dict)
        and cached.get("token")
        and (time.monotonic() - cached.get("ts", 0.0)) < _VAULT_CLIENT_TTL
    ):
        return str(cached["token"])

    try:
        import hvac  # type: ignore[import-untyped]  # noqa: PLC0415

        client = hvac.Client(url=addr, timeout=timeout)
        response = client.auth.approle.login(role_id=role_id, secret_id=secret_id)
        token = str(response.get("auth", {}).get("client_token", ""))
        if token:
            logger.info("Authenticated to OpenBao/Vault at %s via AppRole", addr)
            _vault_client_cache[cache_key] = {"token": token, "ts": time.monotonic()}
            return token
        logger.warning("AppRole login succeeded but returned no token at %s", addr)
        return ""
    except ImportError:
        logger.debug("hvac package not installed — AppRole auth disabled")
        return ""
    except Exception:
        logger.debug("AppRole login failed at %s", addr, exc_info=True)
        return ""


def _get_vault_client(addr: str, token: str, *, timeout: int = 10) -> Any:
    """Construct or return a cached hvac client with TTL-based refresh."""
    cache_key = f"{addr}|{token}"
    if (
        cache_key in _vault_client_cache
        and (time.monotonic() - _vault_client_cache.get("__ts__", 0.0)) < _VAULT_CLIENT_TTL
    ):
        return _vault_client_cache[cache_key]

    try:
        import hvac  # type: ignore[import-untyped]  # noqa: PLC0415

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
            _vault_client_cache["__ts__"] = time.monotonic()
            return client
        logger.warning("Vault authentication failed at %s", addr)
        return None
    except ImportError:
        logger.debug("hvac package not installed — Vault integration disabled")
        return None
    except Exception:
        logger.debug("Vault connection failed", exc_info=True)
        return None
