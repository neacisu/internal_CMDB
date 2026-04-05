"""Runtime Settings Store — DB-backed key/value configuration with in-memory cache.

Reads and writes ``config.app_setting`` rows.  A 60-second TTL cache prevents
a DB hit on every API request while keeping the system responsive to changes.

Public surface::

    from internalcmdb.config.settings_store import get_settings_store

    store = get_settings_store()
    value = await store.get("llm.reasoning.url")          # Any
    await store.set("llm.reasoning.url", "http://...", updated_by="admin")
    group = await store.get_group("llm")                  # dict[str, Any]
    await store.reset_to_default("llm.reasoning.url")
    all_groups = await store.get_all_groups()             # dict[str, dict[str, Any]]
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from typing import Any
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit

logger = logging.getLogger(__name__)

_CACHE_TTL_SECONDS = 60.0
_SECRET_MASK = "***"


class _CacheEntry:
    __slots__ = ("value", "expires_at")

    def __init__(self, value: Any, ttl: float) -> None:
        self.value = value
        self.expires_at = time.monotonic() + ttl


def _build_sync_url(database_url: str) -> str:
    """Normalize a database URL for sync psycopg use on the same host as PostgreSQL.

    The application ``DATABASE_URL`` / ``POSTGRES_SSLMODE`` may carry
    ``sslmode=require`` intended for external/remote clients.  When the API
    runs on the same host as PostgreSQL (network_mode: host), SSL at the DB
    level is unnecessary — SSL for external clients is handled by the Traefik
    TCP SNI proxy layer.  Forcing ``sslmode=require`` on a PostgreSQL instance
    that has no SSL certificate configured causes an immediate
    ``ConnectionResetError`` / "SSL error: unexpected eof while reading".

    Additionally, the public ``POSTGRES_HOST`` may be an external DNS name
    routed through Traefik TCP SNI proxying (which mandates TLS). The
    ``POSTGRES_SYNC_HOST`` / ``POSTGRES_SYNC_PORT`` env vars allow overriding
    the host/port to a direct local address (e.g. ``127.0.0.1:5433``) that
    bypasses Traefik entirely.

    This function:
    1. Replaces host/port with ``POSTGRES_SYNC_HOST``/``POSTGRES_SYNC_PORT``
       if those env vars are set.
    2. Strips any existing ``sslmode`` parameter and forces ``sslmode=disable``
       so the psycopg driver never negotiates SSL.
    """
    parts = urlsplit(database_url)

    sync_host = os.environ.get("POSTGRES_SYNC_HOST", "").strip()
    sync_port = os.environ.get("POSTGRES_SYNC_PORT", "").strip()

    netloc = parts.netloc
    if sync_host or sync_port:
        # netloc may be "user:pass@host:port" — replace only the host[:port] part
        at = netloc.rfind("@")
        userinfo = netloc[: at + 1] if at != -1 else ""
        hostport = netloc[at + 1 :]
        host_only = hostport.rsplit(":", 1)[0] if ":" in hostport else hostport
        new_host = sync_host if sync_host else host_only
        existing_port = hostport.rsplit(":", 1)[1] if ":" in hostport else "5432"
        new_port = sync_port if sync_port else existing_port
        netloc = f"{userinfo}{new_host}:{new_port}"

    params = parse_qs(parts.query, keep_blank_values=True)
    params.pop("sslmode", None)
    params["sslmode"] = ["disable"]
    return urlunsplit(parts._replace(netloc=netloc, query=urlencode(params, doseq=True)))


class SettingsStore:
    """Async key/value store backed by ``config.app_setting``.

    All writes update the DB immediately and invalidate the in-process cache.
    All reads are served from cache when fresh; otherwise fetched from DB.

    Secret values (``is_secret = true``) are stored as plaintext in DB and
    masked as ``"***"`` in all public get operations.  Use ``get_raw_secret``
    to retrieve the unmasked value within trusted server-side code.

    A single SQLAlchemy sync engine is created at construction time and reused
    for all DB calls (thread-safe connection pool).  Per-call engine
    create/dispose is explicitly avoided — it created N connection pools where
    N = number of concurrent requests, causing pool exhaustion.
    """

    def __init__(self, database_url: str, *, cache_ttl: float = _CACHE_TTL_SECONDS) -> None:
        from sqlalchemy import create_engine  # noqa: PLC0415

        self._cache_ttl = cache_ttl
        self._cache: dict[str, _CacheEntry] = {}
        self._lock = asyncio.Lock()
        # Build a normalized sync URL (sslmode=disable) once at init.
        self._sync_url = _build_sync_url(database_url)
        self._engine = create_engine(
            self._sync_url,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=5,
        )

    def close(self) -> None:
        """Dispose the connection pool.  Call during application shutdown."""
        self._engine.dispose()

    # ------------------------------------------------------------------
    # Low-level DB helpers (sync, offloaded to thread via asyncio.to_thread)
    # ------------------------------------------------------------------

    def _fetch_one(self, key: str) -> dict[str, Any] | None:
        from sqlalchemy import text  # noqa: PLC0415

        with self._engine.connect() as conn:
            row = conn.execute(
                text("""
                    SELECT setting_key, setting_group, value_jsonb, default_jsonb,
                           type_hint, description, is_secret, requires_restart,
                           updated_at, updated_by
                    FROM config.app_setting
                    WHERE setting_key = :key
                """),
                {"key": key},
            ).fetchone()
        return dict(row._mapping) if row else None

    def _fetch_group(self, group: str) -> list[dict[str, Any]]:
        from sqlalchemy import text  # noqa: PLC0415

        with self._engine.connect() as conn:
            rows = conn.execute(
                text("""
                    SELECT setting_key, setting_group, value_jsonb, default_jsonb,
                           type_hint, description, is_secret, requires_restart,
                           updated_at, updated_by
                    FROM config.app_setting
                    WHERE setting_group = :group
                    ORDER BY setting_key
                """),
                {"group": group},
            ).fetchall()
        return [dict(r._mapping) for r in rows]

    def _fetch_all(self) -> list[dict[str, Any]]:
        from sqlalchemy import text  # noqa: PLC0415

        with self._engine.connect() as conn:
            rows = conn.execute(
                text("""
                    SELECT setting_key, setting_group, value_jsonb, default_jsonb,
                           type_hint, description, is_secret, requires_restart,
                           updated_at, updated_by
                    FROM config.app_setting
                    ORDER BY setting_group, setting_key
                """)
            ).fetchall()
        return [dict(r._mapping) for r in rows]

    def _upsert_row(
        self,
        key: str,
        value: Any,
        updated_by: str,
    ) -> dict[str, Any]:
        from sqlalchemy import text  # noqa: PLC0415

        with self._engine.connect() as conn:
            row = conn.execute(
                text("""
                    UPDATE config.app_setting
                       SET value_jsonb = :val::jsonb,
                           updated_at  = now(),
                           updated_by  = :by
                     WHERE setting_key = :key
                    RETURNING setting_key, setting_group, value_jsonb, default_jsonb,
                              type_hint, description, is_secret, requires_restart,
                              updated_at, updated_by
                """),
                {"val": json.dumps(value), "by": updated_by, "key": key},
            ).fetchone()
            conn.commit()
        if row is None:
            raise KeyError(f"Setting not found: {key!r}")
        return dict(row._mapping)

    def _reset_row(self, key: str, updated_by: str) -> dict[str, Any]:
        from sqlalchemy import text  # noqa: PLC0415

        with self._engine.connect() as conn:
            row = conn.execute(
                text("""
                    UPDATE config.app_setting
                       SET value_jsonb = default_jsonb,
                           updated_at  = now(),
                           updated_by  = :by
                     WHERE setting_key = :key
                    RETURNING setting_key, setting_group, value_jsonb, default_jsonb,
                              type_hint, description, is_secret, requires_restart,
                              updated_at, updated_by
                """),
                {"key": key, "by": updated_by},
            ).fetchone()
            conn.commit()
        if row is None:
            raise KeyError(f"Setting not found: {key!r}")
        return dict(row._mapping)

    # ------------------------------------------------------------------
    # Cache helpers
    # ------------------------------------------------------------------

    def _cache_hit(self, key: str) -> Any | None:
        entry = self._cache.get(key)
        if entry and time.monotonic() < entry.expires_at:
            return entry.value
        return None

    def _cache_put(self, key: str, value: Any) -> None:
        self._cache[key] = _CacheEntry(value, self._cache_ttl)

    def _cache_invalidate(self, key: str) -> None:
        self._cache.pop(key, None)
        # Also invalidate group/all-groups caches keyed by prefix
        group_prefix = f"__group__{key.split('.')[0]}"
        self._cache.pop(group_prefix, None)
        self._cache.pop("__all__", None)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @staticmethod
    def _mask_if_secret(row: dict[str, Any]) -> dict[str, Any]:
        if row.get("is_secret"):
            row = dict(row)
            row["value_jsonb"] = _SECRET_MASK
        return row

    async def get_row(self, key: str, *, mask_secrets: bool = True) -> dict[str, Any] | None:
        """Return the full DB row for ``key``, or ``None`` if not found.

        Secrets are masked unless ``mask_secrets=False`` (internal use only).
        Returns ``None`` — rather than raising — on transient DB errors (connection
        failure, table not yet migrated) so callers can fall back to safe defaults.
        """
        cache_key = f"__row__{key}"
        cached = self._cache_hit(cache_key)
        if cached is not None:
            return self._mask_if_secret(cached) if mask_secrets else cached

        try:
            row = await asyncio.to_thread(self._fetch_one, key)
        except Exception as exc:
            logger.warning(
                "settings_store.get_row: DB unavailable for key %r — returning None "
                "(check migration status and DB connectivity). error=%s",
                key,
                exc,
            )
            return None
        if row is None:
            return None

        self._cache_put(cache_key, row)
        return self._mask_if_secret(row) if mask_secrets else row

    async def get(self, key: str) -> Any:
        """Return the parsed ``value_jsonb`` for ``key``.

        Falls back to ``default_jsonb`` if the setting is not found in DB.
        Secret values are returned as ``"***"`` — use ``get_raw_secret`` for trusted reads.
        """
        row = await self.get_row(key, mask_secrets=False)
        if row is None:
            logger.warning("settings_store.get: key %r not found, returning None", key)
            return None
        if row.get("is_secret"):
            return _SECRET_MASK
        return row["value_jsonb"]

    async def get_raw_secret(self, key: str) -> Any:
        """Return the unmasked value for a secret setting.

        Only call this from server-side trusted code (e.g. LLMClient constructor).
        Never expose the result in an API response.
        """
        row = await self.get_row(key, mask_secrets=False)
        if row is None:
            return None
        return row["value_jsonb"]

    async def get_group(self, group: str, *, mask_secrets: bool = True) -> list[dict[str, Any]]:
        """Return all rows for a setting group, sorted by key."""
        cache_key = f"__group__{group}"
        cached = self._cache_hit(cache_key)
        if cached is not None:
            return [self._mask_if_secret(r) if mask_secrets else r for r in cached]

        try:
            rows = await asyncio.to_thread(self._fetch_group, group)
        except Exception as exc:
            logger.warning(
                "settings_store.get_group: DB unavailable for group %r — returning []. error=%s",
                group,
                exc,
            )
            return []
        self._cache_put(cache_key, rows)
        return [self._mask_if_secret(r) if mask_secrets else r for r in rows]

    async def get_all_groups(self, *, mask_secrets: bool = True) -> dict[str, list[dict[str, Any]]]:
        """Return all settings grouped by ``setting_group``."""
        cached = self._cache_hit("__all__")
        if cached is not None:
            return {
                g: [self._mask_if_secret(r) if mask_secrets else r for r in rows]
                for g, rows in cached.items()
            }

        try:
            rows = await asyncio.to_thread(self._fetch_all)
        except Exception as exc:
            logger.warning(
                "settings_store.get_all_groups: DB unavailable — returning {}. error=%s", exc
            )
            return {}
        grouped: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            grouped.setdefault(row["setting_group"], []).append(row)
        self._cache_put("__all__", grouped)
        return {
            g: [self._mask_if_secret(r) if mask_secrets else r for r in rs]
            for g, rs in grouped.items()
        }

    async def set(self, key: str, value: Any, *, updated_by: str) -> dict[str, Any]:
        """Write a new value for ``key`` and invalidate cache.

        Raises ``KeyError`` if the setting does not exist.
        Returns the updated row (secrets masked).
        """
        async with self._lock:
            row = await asyncio.to_thread(self._upsert_row, key, value, updated_by)
            self._cache_invalidate(f"__row__{key}")
            logger.info("settings_store.set: %r updated by %r", key, updated_by)
            return self._mask_if_secret(row)

    async def reset_to_default(self, key: str, *, updated_by: str = "system_reset") -> dict[str, Any]:
        """Reset ``key`` to its ``default_jsonb`` value."""
        async with self._lock:
            row = await asyncio.to_thread(self._reset_row, key, updated_by)
            self._cache_invalidate(f"__row__{key}")
            logger.info("settings_store.reset: %r reset to default", key)
            return self._mask_if_secret(row)

    def invalidate_all(self) -> None:
        """Clear the entire in-process cache (e.g. after bulk seed)."""
        self._cache.clear()


# ---------------------------------------------------------------------------
# Singleton factory
# ---------------------------------------------------------------------------

_store: SettingsStore | None = None


def get_settings_store() -> SettingsStore:
    """Return the process-wide SettingsStore singleton."""
    global _store  # noqa: PLW0603
    if _store is None:
        from internalcmdb.api.config import get_settings  # noqa: PLC0415
        settings = get_settings()
        _store = SettingsStore(str(settings.database_url))
    return _store


def close_settings_store() -> None:
    """Dispose the SettingsStore singleton engine.  Call during app shutdown."""
    global _store  # noqa: PLW0603
    if _store is not None:
        _store.close()
        _store = None
