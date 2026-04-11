"""Settings router — runtime configuration management.

All write endpoints require the ``admin`` role.
All read endpoints require one of: ``admin``, ``operator``, ``viewer``.
User-preference endpoints require only a valid Bearer token (own data).

Security notes:
  - Secret values are never returned in API responses (masked as "***")
  - HMAC webhook secrets are stored as SHA-256 hex hash (OWASP A02)
  - target_url validated to http/https scheme only (OWASP A03)
  - user_id always taken from JWT sub claim, never from request body (OWASP A01 BOLA)
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import sys
import time
import uuid
from typing import Any, cast

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import CursorResult, text
from sqlalchemy.ext.asyncio import AsyncSession

from internalcmdb.api.deps import get_async_session
from internalcmdb.api.middleware.rbac import AUTH_DEV_MODE, require_role
from internalcmdb.api.schemas.settings import (
    AppSettingOut,
    AppSettingUpdate,
    GuardConfig,
    GuardConfigUpdate,
    HITLConfig,
    HITLConfigUpdate,
    LLMBackendStatus,
    LLMConfigOut,
    LLMConfigUpdate,
    LLMModelConfig,
    NotificationChannelCreate,
    NotificationChannelOut,
    NotificationChannelUpdate,
    ObservabilityConfig,
    ObservabilityConfigUpdate,
    RetentionConfig,
    RetentionConfigUpdate,
    SelfHealConfig,
    SelfHealConfigUpdate,
    SettingGroupOut,
    SystemInfoOut,
    TestNotificationResult,
    TokenBudgetConfig,
    TokenBudgetUpdate,
    UserPreferenceOut,
    UserPreferenceUpdate,
)
from internalcmdb.config.settings_store import SettingsStore, get_settings_store

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/settings", tags=["settings"])

_READER_ROLES = ("admin", "operator", "viewer")
_TOOL_ALLOWLIST = [
    "query_registry",
    "list_hosts",
    "list_services",
    "get_host_facts",
    "get_service_instances",
    "search_documents",
    "get_health_score",
    "list_insights",
    "generate_report",
    "check_drift",
    "run_collector",
    "list_evidence_packs",
]
_MAX_ACTIONS: dict[str, int] = {
    "agent-audit": 50,
    "agent-capacity": 30,
    "cognitive-query": 20,
    "report-generator": 10,
    "default": 15,
}
_TOKEN_BUDGET_CALLERS = [
    "agent_audit",
    "agent_capacity",
    "agent_security",
    "cognitive_query",
    "report_generator",
    "chaos_engine",
    "default",
]
_LLM_PROBE_TIMEOUT = 3.0  # seconds per health probe

# ---------------------------------------------------------------------------
# Setting-key constants (S1192 — prevent duplicate literal violations)
# ---------------------------------------------------------------------------
_SK_GUARD_URL = "llm.guard.url"
_SK_OBS_DEBUG = "obs.debug_enabled"
_MSG_CHANNEL_NOT_FOUND = "Notification channel not found"

# Default values for each LLM backend: (url, model_id, timeout_s).
# Single source of truth — used by _resolve_llm_backend and get_system_info.
# SONAR-HOTSPOT REVIEWED: S1075 / S5332 — These are private LAN addresses for
# self-hosted Proxmox LXC containers (RFC-1918, not publicly routable).
# All values are overridable via DB SettingsStore.  HTTP over internal LAN only.
# Mirrors _DEFAULT_*_URL constants in internalcmdb.llm.client.  ACCEPTED.
_LLM_BACKEND_DEFAULTS: dict[str, tuple[str, str, int]] = {
    "reasoning": ("http://10.0.1.10:49001", "Qwen/QwQ-32B-AWQ", 120),
    "fast": ("http://10.0.1.10:49002", "Qwen/Qwen2.5-14B-Instruct-AWQ", 60),
    "embed": ("http://10.0.1.10:49003", "qwen3-embedding-8b-q5km", 30),
    "guard": ("http://10.0.1.115:8000", "llm-guard", 15),
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _store() -> SettingsStore:
    return get_settings_store()


def _user_id_from_request(request: Request) -> str:
    """Extract user_id from JWT sub claim.

    Cookie is checked first, then Bearer header.
    Falls back to 'dev' in AUTH_DEV_MODE, otherwise 'anonymous'.
    This prevents BOLA — user_id is NEVER taken from request body.
    """
    from internalcmdb.api.config import get_settings  # noqa: PLC0415
    from internalcmdb.auth.security import decode_access_token  # noqa: PLC0415

    if AUTH_DEV_MODE:
        return "dev"

    settings = get_settings()
    token: str | None = request.cookies.get(settings.jwt_cookie_name)
    if not token:
        auth = request.headers.get("authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]

    if token:
        try:
            payload = decode_access_token(token)
            return payload.sub
        except Exception:
            logger.debug("JWT decode failed, defaulting to anonymous", exc_info=True)
    return "anonymous"


def _sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


async def _probe_llm_backend(name: str, url: str, model: str) -> LLMBackendStatus:
    """Probe one LLM backend and return its live status."""
    probe_urls: dict[str, str] = {
        "embed": f"{url}/api/version",
        "guard": f"{url}/health",
    }
    check_url = probe_urls.get(name, f"{url}/health")

    start = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=_LLM_PROBE_TIMEOUT) as client:
            resp = await client.get(check_url)
        ms = int((time.monotonic() - start) * 1000)
        return LLMBackendStatus(
            name=name,
            model=model,
            url=url,
            reachable=resp.status_code < 500,  # noqa: PLR2004
            response_ms=ms,
        )
    except Exception as exc:
        ms = int((time.monotonic() - start) * 1000)
        return LLMBackendStatus(
            name=name,
            model=model,
            url=url,
            reachable=False,
            response_ms=ms,
            error=type(exc).__name__,
        )


async def _resolve_llm_backend(store: SettingsStore, name: str) -> LLMModelConfig:
    """Fetch URL / model_id / timeout_s for one LLM backend from settings.

    Falls back to ``_LLM_BACKEND_DEFAULTS[name]`` for any key not yet in DB.
    Centralises all per-backend setting reads — eliminates the previously
    repeated ``store.get("llm.<name>.<field>")`` calls across multiple functions.
    """
    default_url, default_mid, default_tmo = _LLM_BACKEND_DEFAULTS[name]
    url = await store.get(f"llm.{name}.url") or default_url
    model_id = await store.get(f"llm.{name}.model_id") or default_mid
    timeout_s = await store.get(f"llm.{name}.timeout_s") or default_tmo
    return LLMModelConfig(url=str(url), model_id=str(model_id), timeout_s=int(timeout_s))


# ---------------------------------------------------------------------------
# Generic raw settings (for operator inspection)
# ---------------------------------------------------------------------------


@router.get(
    "",
    response_model=list[SettingGroupOut],
    dependencies=[Depends(require_role(*_READER_ROLES))],
    summary="List all settings grouped by domain",
)
async def list_all_settings() -> list[SettingGroupOut]:
    groups_data = await _store().get_all_groups(mask_secrets=True)
    return [
        SettingGroupOut(
            group=group,
            settings=[AppSettingOut.from_row(r) for r in rows],
        )
        for group, rows in sorted(groups_data.items())
    ]


@router.get(
    "/group/{group}",
    response_model=SettingGroupOut,
    dependencies=[Depends(require_role(*_READER_ROLES))],
    summary="Get all settings for one group",
)
async def get_settings_group(group: str) -> SettingGroupOut:
    rows = await _store().get_group(group, mask_secrets=True)
    if not rows:
        raise HTTPException(status_code=404, detail=f"Settings group '{group}' not found")
    return SettingGroupOut(group=group, settings=[AppSettingOut.from_row(r) for r in rows])


@router.put(
    "/{setting_key:path}",
    response_model=AppSettingOut,
    dependencies=[Depends(require_role("admin"))],
    summary="Update a single setting value",
)
async def update_setting(
    setting_key: str, body: AppSettingUpdate, request: Request
) -> AppSettingOut:
    # Reject keys that contain path traversal patterns
    if ".." in setting_key or "/" in setting_key:
        raise HTTPException(status_code=400, detail="Invalid setting key")
    user = _user_id_from_request(request)
    try:
        row = await _store().set(setting_key, body.value, updated_by=user)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Setting '{setting_key}' not found") from exc
    return AppSettingOut.from_row(row)


@router.post(
    "/{setting_key:path}/reset",
    response_model=AppSettingOut,
    dependencies=[Depends(require_role("admin"))],
    summary="Reset a setting to its default value",
)
async def reset_setting(setting_key: str) -> AppSettingOut:
    if ".." in setting_key or "/" in setting_key:
        raise HTTPException(status_code=400, detail="Invalid setting key")
    try:
        row = await _store().reset_to_default(setting_key)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Setting '{setting_key}' not found") from exc
    return AppSettingOut.from_row(row)


# ---------------------------------------------------------------------------
# LLM configuration
# ---------------------------------------------------------------------------


async def _build_llm_config() -> LLMConfigOut:
    store = _store()
    guard_token = await store.get_raw_secret("llm.guard.token")
    return LLMConfigOut(
        reasoning=await _resolve_llm_backend(store, "reasoning"),
        fast=await _resolve_llm_backend(store, "fast"),
        embed=await _resolve_llm_backend(store, "embed"),
        guard=await _resolve_llm_backend(store, "guard"),
        guard_token_set=bool(guard_token),
        circuit_breaker_threshold=await store.get("llm.circuit_breaker.threshold") or 5,
        circuit_breaker_cooldown_s=await store.get("llm.circuit_breaker.cooldown_s") or 60,
        max_connections=await store.get("llm.pool.max_connections") or 100,
        max_keepalive=await store.get("llm.pool.max_keepalive") or 20,
        max_retries=await store.get("llm.max_retries") or 3,
    )


@router.get(
    "/llm",
    response_model=LLMConfigOut,
    dependencies=[Depends(require_role(*_READER_ROLES))],
    summary="Get LLM backend configuration",
)
async def get_llm_config() -> LLMConfigOut:
    return await _build_llm_config()


@router.get(
    "/llm/health",
    response_model=dict,
    dependencies=[Depends(require_role(*_READER_ROLES))],
    summary="Live reachability check for all 4 LLM backends",
)
async def llm_health_check() -> dict[str, Any]:
    """Probe all 4 LLM backends concurrently and return status + latency."""
    store = _store()
    backends: dict[str, tuple[str, str]] = {}
    for name in ("reasoning", "fast", "embed", "guard"):
        default_url, default_mid, _ = _LLM_BACKEND_DEFAULTS[name]
        url = await store.get(f"llm.{name}.url") or default_url
        model_id = await store.get(f"llm.{name}.model_id") or default_mid
        backends[name] = (str(url), str(model_id))

    _hlt = "/health"
    probe_url_map: dict[str, str] = {
        "embed": "/api/version",
        "reasoning": _hlt,
        "fast": _hlt,
        "guard": _hlt,
    }

    async def _probe(name: str, url: str) -> tuple[str, dict[str, Any]]:
        path = probe_url_map.get(name, _hlt)
        check_url = url.rstrip("/") + path
        start = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=_LLM_PROBE_TIMEOUT) as client:
                resp = await client.get(check_url)
            ms = int((time.monotonic() - start) * 1000)
            return name, {"ok": resp.status_code < 500, "latency_ms": ms, "url": url}  # noqa: PLR2004
        except Exception as exc:
            ms = int((time.monotonic() - start) * 1000)
            return name, {"ok": False, "latency_ms": ms, "url": url, "error": type(exc).__name__}

    results = await asyncio.gather(*[_probe(n, url) for n, (url, _) in backends.items()])
    return dict(results)


@router.put(
    "/llm",
    response_model=LLMConfigOut,
    dependencies=[Depends(require_role("admin"))],
    summary="Update LLM backend configuration",
)
async def update_llm_config(body: LLMConfigUpdate, request: Request) -> LLMConfigOut:
    store = _store()
    user = _user_id_from_request(request)
    field_map: dict[str, str] = {
        "reasoning_url": "llm.reasoning.url",
        "fast_url": "llm.fast.url",
        "embed_url": "llm.embed.url",
        "guard_url": _SK_GUARD_URL,
        "reasoning_model_id": "llm.reasoning.model_id",
        "fast_model_id": "llm.fast.model_id",
        "embed_model_id": "llm.embed.model_id",
        "reasoning_timeout_s": "llm.reasoning.timeout_s",
        "fast_timeout_s": "llm.fast.timeout_s",
        "embed_timeout_s": "llm.embed.timeout_s",
        "guard_timeout_s": "llm.guard.timeout_s",
        "guard_token": "llm.guard.token",
        "circuit_breaker_threshold": "llm.circuit_breaker.threshold",
        "circuit_breaker_cooldown_s": "llm.circuit_breaker.cooldown_s",
        "max_connections": "llm.pool.max_connections",
        "max_keepalive": "llm.pool.max_keepalive",
        "max_retries": "llm.max_retries",
    }
    for field_name, setting_key in field_map.items():
        val = getattr(body, field_name)
        if val is not None:
            await store.set(setting_key, val, updated_by=user)
    store.invalidate_all()
    return await _build_llm_config()


# ---------------------------------------------------------------------------
# Token budgets
# ---------------------------------------------------------------------------


@router.get(
    "/token-budgets",
    response_model=list[TokenBudgetConfig],
    dependencies=[Depends(require_role(*_READER_ROLES))],
    summary="Get per-caller hourly token budgets",
)
async def get_token_budgets() -> list[TokenBudgetConfig]:
    store = _store()
    spike = await store.get("budget.spike_multiplier") or 3.0
    result: list[TokenBudgetConfig] = []
    for caller in _TOKEN_BUDGET_CALLERS:
        key = f"budget.{caller}"
        val = await store.get(key) or 100000
        result.append(
            TokenBudgetConfig(
                caller=caller.replace("_", "-"),
                tokens_per_hour=int(val),
                spike_multiplier=float(spike),
            )
        )
    return result


@router.put(
    "/token-budgets/{caller}",
    response_model=TokenBudgetConfig,
    dependencies=[Depends(require_role("admin"))],
    summary="Update one caller's hourly token budget",
)
async def update_token_budget(
    caller: str, body: TokenBudgetUpdate, request: Request
) -> TokenBudgetConfig:
    normalized = caller.replace("-", "_")
    if normalized not in _TOKEN_BUDGET_CALLERS:
        raise HTTPException(status_code=404, detail=f"Caller '{caller}' not found")
    store = _store()
    user = _user_id_from_request(request)
    key = f"budget.{normalized}"
    await store.set(key, body.tokens_per_hour, updated_by=user)
    spike = await store.get("budget.spike_multiplier") or 3.0
    return TokenBudgetConfig(
        caller=caller,
        tokens_per_hour=body.tokens_per_hour,
        spike_multiplier=float(spike),
    )


# ---------------------------------------------------------------------------
# Guard & safety
# ---------------------------------------------------------------------------


@router.get(
    "/guard",
    response_model=GuardConfig,
    dependencies=[Depends(require_role(*_READER_ROLES))],
    summary="Get guard pipeline and LLM safety configuration",
)
async def get_guard_config() -> GuardConfig:
    store = _store()
    fail_closed_val = await store.get("guard.fail_closed")
    timeout_val = await store.get("guard.timeout_s")
    return GuardConfig(
        fail_closed=fail_closed_val if fail_closed_val is not None else True,
        guard_url=await store.get(_SK_GUARD_URL) or _LLM_BACKEND_DEFAULTS["guard"][0],
        timeout_s=timeout_val if timeout_val is not None else 5.0,
        tool_allowlist=_TOOL_ALLOWLIST,
        max_actions_per_session=_MAX_ACTIONS,
    )


@router.put(
    "/guard",
    response_model=GuardConfig,
    dependencies=[Depends(require_role("admin"))],
    summary="Update guard configuration",
)
async def update_guard_config(body: GuardConfigUpdate, request: Request) -> GuardConfig:
    store = _store()
    user = _user_id_from_request(request)
    if body.fail_closed is not None:
        await store.set("guard.fail_closed", body.fail_closed, updated_by=user)
    if body.timeout_s is not None:
        await store.set("guard.timeout_s", body.timeout_s, updated_by=user)
    store.invalidate_all()
    return await get_guard_config()


# ---------------------------------------------------------------------------
# HITL governance
# ---------------------------------------------------------------------------


@router.get(
    "/hitl",
    response_model=HITLConfig,
    dependencies=[Depends(require_role(*_READER_ROLES))],
    summary="Get HITL escalation thresholds",
)
async def get_hitl_config() -> HITLConfig:
    store = _store()
    return HITLConfig(
        rc4_escalation_minutes=await store.get("hitl.rc4.escalation_minutes") or 15,
        rc3_escalation_minutes=await store.get("hitl.rc3.escalation_minutes") or 60,
        rc2_escalation_hours=await store.get("hitl.rc2.escalation_hours") or 4,
        max_escalations=await store.get("hitl.max_escalations") or 3,
    )


@router.put(
    "/hitl",
    response_model=HITLConfig,
    dependencies=[Depends(require_role("admin"))],
    summary="Update HITL escalation thresholds",
)
async def update_hitl_config(body: HITLConfigUpdate, request: Request) -> HITLConfig:
    store = _store()
    user = _user_id_from_request(request)
    if body.rc4_escalation_minutes is not None:
        await store.set("hitl.rc4.escalation_minutes", body.rc4_escalation_minutes, updated_by=user)
    if body.rc3_escalation_minutes is not None:
        await store.set("hitl.rc3.escalation_minutes", body.rc3_escalation_minutes, updated_by=user)
    if body.rc2_escalation_hours is not None:
        await store.set("hitl.rc2.escalation_hours", body.rc2_escalation_hours, updated_by=user)
    if body.max_escalations is not None:
        await store.set("hitl.max_escalations", body.max_escalations, updated_by=user)
    store.invalidate_all()
    return await get_hitl_config()


# ---------------------------------------------------------------------------
# Self-heal
# ---------------------------------------------------------------------------


@router.get(
    "/self-heal",
    response_model=SelfHealConfig,
    dependencies=[Depends(require_role(*_READER_ROLES))],
    summary="Get self-healing thresholds",
)
async def get_self_heal_config() -> SelfHealConfig:
    store = _store()
    return SelfHealConfig(
        disk_threshold_pct=await store.get("self_heal.disk_threshold_pct") or 85,
        log_auto_truncate_bytes=await store.get("self_heal.log_auto_truncate_bytes") or 2147483648,
        log_hitl_bytes=await store.get("self_heal.log_hitl_bytes") or 524288000,
    )


@router.put(
    "/self-heal",
    response_model=SelfHealConfig,
    dependencies=[Depends(require_role("admin"))],
    summary="Update self-healing thresholds",
)
async def update_self_heal_config(body: SelfHealConfigUpdate, request: Request) -> SelfHealConfig:
    store = _store()
    user = _user_id_from_request(request)
    if body.disk_threshold_pct is not None:
        await store.set("self_heal.disk_threshold_pct", body.disk_threshold_pct, updated_by=user)
    if body.log_auto_truncate_bytes is not None:
        await store.set(
            "self_heal.log_auto_truncate_bytes", body.log_auto_truncate_bytes, updated_by=user
        )
    if body.log_hitl_bytes is not None:
        await store.set("self_heal.log_hitl_bytes", body.log_hitl_bytes, updated_by=user)
    store.invalidate_all()
    return await get_self_heal_config()


# ---------------------------------------------------------------------------
# Retention
# ---------------------------------------------------------------------------


@router.get(
    "/retention",
    response_model=RetentionConfig,
    dependencies=[Depends(require_role(*_READER_ROLES))],
    summary="Get data retention configuration (days per table)",
)
async def get_retention_config() -> RetentionConfig:
    store = _store()
    return RetentionConfig(
        job_history_days=await store.get("retention.job_history_days") or 90,
        audit_events_days=await store.get("retention.audit_events_days") or 365,
        snapshots_days=await store.get("retention.snapshots_days") or 30,
        llm_calls_days=await store.get("retention.llm_calls_days") or 90,
        metric_points_days=await store.get("retention.metric_points_days") or 30,
        insights_days=await store.get("retention.insights_days") or 180,
    )


@router.put(
    "/retention",
    response_model=RetentionConfig,
    dependencies=[Depends(require_role("admin"))],
    summary="Update data retention windows",
)
async def update_retention_config(body: RetentionConfigUpdate, request: Request) -> RetentionConfig:
    store = _store()
    user = _user_id_from_request(request)
    field_map = {
        "job_history_days": "retention.job_history_days",
        "audit_events_days": "retention.audit_events_days",
        "snapshots_days": "retention.snapshots_days",
        "llm_calls_days": "retention.llm_calls_days",
        "metric_points_days": "retention.metric_points_days",
        "insights_days": "retention.insights_days",
    }
    for field_name, key in field_map.items():
        val = getattr(body, field_name)
        if val is not None:
            await store.set(key, val, updated_by=user)
    store.invalidate_all()
    return await get_retention_config()


# ---------------------------------------------------------------------------
# Observability
# ---------------------------------------------------------------------------


@router.get(
    "/observability",
    response_model=ObservabilityConfig,
    dependencies=[Depends(require_role(*_READER_ROLES))],
    summary="Get observability and application runtime config",
)
async def get_observability_config() -> ObservabilityConfig:
    store = _store()
    cors_raw = await store.get("obs.cors_origins")
    cors: list[str] = (
        [str(c) for c in cors_raw] if isinstance(cors_raw, list) else ["http://localhost:3333"]
    )
    insecure_val = await store.get("obs.otlp_insecure")
    sample_val = await store.get("obs.sample_rate")
    debug_val = await store.get(_SK_OBS_DEBUG)
    return ObservabilityConfig(
        otlp_endpoint=await store.get("obs.otlp_endpoint") or "http://localhost:4317",
        otlp_protocol=await store.get("obs.otlp_protocol") or "grpc",
        otlp_insecure=insecure_val if insecure_val is not None else True,
        sample_rate=sample_val if sample_val is not None else 1.0,
        log_level=await store.get("obs.log_level") or "INFO",
        debug_enabled=debug_val if debug_val is not None else True,
        cors_origins=cors,
    )


@router.put(
    "/observability",
    response_model=ObservabilityConfig,
    dependencies=[Depends(require_role("admin"))],
    summary="Update observability configuration (most fields require restart)",
)
async def update_observability_config(
    body: ObservabilityConfigUpdate, request: Request
) -> ObservabilityConfig:
    store = _store()
    user = _user_id_from_request(request)
    field_map = {
        "otlp_endpoint": "obs.otlp_endpoint",
        "otlp_protocol": "obs.otlp_protocol",
        "otlp_insecure": "obs.otlp_insecure",
        "sample_rate": "obs.sample_rate",
        "log_level": "obs.log_level",
        "debug_enabled": _SK_OBS_DEBUG,
        "cors_origins": "obs.cors_origins",
    }
    for field_name, key in field_map.items():
        val = getattr(body, field_name)
        if val is not None:
            await store.set(key, val, updated_by=user)
    store.invalidate_all()
    return await get_observability_config()


# ---------------------------------------------------------------------------
# Notification channels
# ---------------------------------------------------------------------------


def _channel_row_to_out(row: dict[str, Any]) -> NotificationChannelOut:
    return NotificationChannelOut(
        channel_id=str(row["channel_id"]),
        name=row["name"],
        channel_type=row["channel_type"],
        target_url=row.get("target_url"),
        events=row.get("events") or [],
        is_active=row.get("is_active", True),
        hmac_configured=bool(row.get("hmac_secret_hash")),
        created_at=row.get("created_at"),
        updated_at=row.get("updated_at"),
    )


@router.get(
    "/notifications",
    response_model=list[NotificationChannelOut],
    dependencies=[Depends(require_role(*_READER_ROLES))],
    summary="List all notification channels",
)
async def list_notification_channels(
    session: AsyncSession = Depends(get_async_session),  # noqa: B008
) -> list[NotificationChannelOut]:
    result = await session.execute(
        text("""
            SELECT channel_id, name, channel_type, target_url,
                   hmac_secret_hash, events, is_active, created_at, updated_at
            FROM config.notification_channel
            ORDER BY created_at DESC
        """)
    )
    return [_channel_row_to_out(dict(r._mapping)) for r in result.fetchall()]


@router.post(
    "/notifications",
    response_model=NotificationChannelOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role("admin"))],
    summary="Create a new notification channel",
)
async def create_notification_channel(
    body: NotificationChannelCreate,
    session: AsyncSession = Depends(get_async_session),  # noqa: B008
) -> NotificationChannelOut:
    hmac_hash = _sha256_hex(body.hmac_secret) if body.hmac_secret else None
    result = await session.execute(
        text("""
            INSERT INTO config.notification_channel
                (name, channel_type, target_url, hmac_secret_hash, events, is_active)
            VALUES
                (:name, 'webhook', :url, :hmac_hash, :events, :active)
            RETURNING channel_id, name, channel_type, target_url,
                      hmac_secret_hash, events, is_active, created_at, updated_at
        """),
        {
            "name": body.name,
            "url": body.target_url,
            "hmac_hash": hmac_hash,
            "events": body.events,
            "active": body.is_active,
        },
    )
    await session.commit()
    row = result.fetchone()
    if row is None:  # INSERT … RETURNING must always yield a row; guard for type safety
        raise HTTPException(status_code=500, detail="Channel creation failed unexpectedly")
    return _channel_row_to_out(dict(row._mapping))


@router.get(
    "/notifications/{channel_id}",
    response_model=NotificationChannelOut,
    dependencies=[Depends(require_role(*_READER_ROLES))],
    summary="Get a single notification channel",
)
async def get_notification_channel(
    channel_id: str,
    session: AsyncSession = Depends(get_async_session),  # noqa: B008
) -> NotificationChannelOut:
    _validate_uuid(channel_id)
    result = await session.execute(
        text("""
            SELECT channel_id, name, channel_type, target_url,
                   hmac_secret_hash, events, is_active, created_at, updated_at
            FROM config.notification_channel
            WHERE channel_id = :cid
        """),
        {"cid": channel_id},
    )
    row = result.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=_MSG_CHANNEL_NOT_FOUND)
    return _channel_row_to_out(dict(row._mapping))


@router.put(
    "/notifications/{channel_id}",
    response_model=NotificationChannelOut,
    dependencies=[Depends(require_role("admin"))],
    summary="Update a notification channel",
)
async def update_notification_channel(
    channel_id: str,
    body: NotificationChannelUpdate,
    session: AsyncSession = Depends(get_async_session),  # noqa: B008
) -> NotificationChannelOut:
    _validate_uuid(channel_id)
    updates: list[str] = ["updated_at = now()"]
    params: dict[str, Any] = {"cid": channel_id}
    if body.name is not None:
        updates.append("name = :name")
        params["name"] = body.name
    if body.target_url is not None:
        updates.append("target_url = :url")
        params["url"] = body.target_url
    if body.hmac_secret is not None:
        updates.append("hmac_secret_hash = :hmac_hash")
        params["hmac_hash"] = _sha256_hex(body.hmac_secret)
    if body.events is not None:
        updates.append("events = :events")
        params["events"] = body.events
    if body.is_active is not None:
        updates.append("is_active = :active")
        params["active"] = body.is_active

    sql = (
        "UPDATE config.notification_channel SET " + ", ".join(updates) + " WHERE channel_id = :cid"
        " RETURNING channel_id, name, channel_type, target_url,"
        "           hmac_secret_hash, events, is_active, created_at, updated_at"
    )
    result = await session.execute(
        text(sql),
        params,
    )
    await session.commit()
    row = result.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=_MSG_CHANNEL_NOT_FOUND)
    return _channel_row_to_out(dict(row._mapping))


@router.delete(
    "/notifications/{channel_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_role("admin"))],
    summary="Delete a notification channel",
)
async def delete_notification_channel(
    channel_id: str,
    session: AsyncSession = Depends(get_async_session),  # noqa: B008
) -> None:
    _validate_uuid(channel_id)
    result = await session.execute(
        text("DELETE FROM config.notification_channel WHERE channel_id = :cid"),
        {"cid": channel_id},
    )
    await session.commit()
    if cast(CursorResult[Any], result).rowcount == 0:
        raise HTTPException(status_code=404, detail=_MSG_CHANNEL_NOT_FOUND)


@router.post(
    "/notifications/{channel_id}/test",
    response_model=TestNotificationResult,
    dependencies=[Depends(require_role("admin"))],
    summary="Send a test event to a notification channel",
)
async def probe_notification_channel(
    channel_id: str,
    session: AsyncSession = Depends(get_async_session),  # noqa: B008
) -> TestNotificationResult:
    _validate_uuid(channel_id)
    result = await session.execute(
        text(
            "SELECT target_url, hmac_secret_hash "
            "FROM config.notification_channel WHERE channel_id = :cid"
        ),
        {"cid": channel_id},
    )
    row = result.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=_MSG_CHANNEL_NOT_FOUND)

    target_url = row[0]
    hmac_hash = row[1]
    if not target_url:
        return TestNotificationResult(success=False, error="No target_url configured")

    payload = json.dumps({"event": "test", "source": "infraq.app/settings"})
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if hmac_hash:
        # We only have the hash — send a placeholder header indicating HMAC is configured
        headers["X-CMDB-HMAC-Configured"] = "true"

    start = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(target_url, content=payload, headers=headers)
        ms = int((time.monotonic() - start) * 1000)
        return TestNotificationResult(
            success=resp.status_code < 400,  # noqa: PLR2004
            status_code=resp.status_code,
            latency_ms=ms,
        )
    except Exception as exc:
        ms = int((time.monotonic() - start) * 1000)
        return TestNotificationResult(
            success=False,
            error=type(exc).__name__,
            latency_ms=ms,
        )


# ---------------------------------------------------------------------------
# User preferences
# ---------------------------------------------------------------------------


@router.get(
    "/preferences",
    response_model=list[UserPreferenceOut],
    summary="Get all preferences for the authenticated user",
)
async def get_user_preferences(
    request: Request,
    session: AsyncSession = Depends(get_async_session),  # noqa: B008
) -> list[UserPreferenceOut]:
    user_id = _user_id_from_request(request)
    result = await session.execute(
        text("""
            SELECT preference_key, value_jsonb, updated_at
            FROM config.user_preference
            WHERE user_id = :uid
            ORDER BY preference_key
        """),
        {"uid": user_id},
    )
    return [
        UserPreferenceOut(
            preference_key=r[0],
            value=r[1],
            updated_at=r[2],
        )
        for r in result.fetchall()
    ]


@router.put(
    "/preferences/{preference_key}",
    response_model=UserPreferenceOut,
    summary="Set or update a user preference",
)
async def update_user_preference(
    preference_key: str,
    body: UserPreferenceUpdate,
    request: Request,
    session: AsyncSession = Depends(get_async_session),  # noqa: B008
) -> UserPreferenceOut:
    if ".." in preference_key or "/" in preference_key:
        raise HTTPException(status_code=400, detail="Invalid preference key")
    user_id = _user_id_from_request(request)
    result = await session.execute(
        text("""
            INSERT INTO config.user_preference (user_id, preference_key, value_jsonb)
            VALUES (:uid, :key, :val::jsonb)
            ON CONFLICT (user_id, preference_key)
            DO UPDATE SET value_jsonb = :val::jsonb, updated_at = now()
            RETURNING preference_key, value_jsonb, updated_at
        """),
        {"uid": user_id, "key": preference_key, "val": json.dumps(body.value)},
    )
    await session.commit()
    row = result.fetchone()
    if row is None:  # INSERT … RETURNING must always yield a row; guard for type safety
        raise HTTPException(status_code=500, detail="Preference update failed unexpectedly")
    return UserPreferenceOut(preference_key=row[0], value=row[1], updated_at=row[2])


@router.delete(
    "/preferences/{preference_key}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a user preference",
)
async def delete_user_preference(
    preference_key: str,
    request: Request,
    session: AsyncSession = Depends(get_async_session),  # noqa: B008
) -> None:
    if ".." in preference_key or "/" in preference_key:
        raise HTTPException(status_code=400, detail="Invalid preference key")
    user_id = _user_id_from_request(request)
    await session.execute(
        text("DELETE FROM config.user_preference WHERE user_id = :uid AND preference_key = :key"),
        {"uid": user_id, "key": preference_key},
    )
    await session.commit()


# ---------------------------------------------------------------------------
# System info (read-only, live health probes)
# ---------------------------------------------------------------------------


@router.get(
    "/system-info",
    response_model=SystemInfoOut,
    dependencies=[Depends(require_role(*_READER_ROLES))],
    summary="Read-only system information with live LLM backend health probes",
)
async def get_system_info() -> SystemInfoOut:
    from internalcmdb.api.config import get_settings  # noqa: PLC0415
    from internalcmdb.workers.cognitive_tasks import COGNITIVE_TASKS  # noqa: PLC0415
    from internalcmdb.workers.queue import WorkerSettings  # noqa: PLC0415

    app_settings = get_settings()
    store = _store()

    # DB connection info — no credentials
    db_host = app_settings.postgres_host
    db_port = app_settings.postgres_port
    db_name = app_settings.postgres_db
    db_ssl = app_settings.postgres_sslmode

    # Redis — host:port only
    redis_url = app_settings.redis_url
    try:
        from urllib.parse import urlsplit  # noqa: PLC0415

        r = urlsplit(redis_url)
        redis_host = f"{r.hostname}:{r.port or 6379}"
    except Exception:
        redis_host = redis_url.split("@")[-1] if "@" in redis_url else redis_url

    # LLM backend probes — all in parallel, 3s timeout each.
    # _resolve_llm_backend reads URL/model_id from settings with fallback to _LLM_BACKEND_DEFAULTS.
    llm_cfgs = {name: await _resolve_llm_backend(store, name) for name in _LLM_BACKEND_DEFAULTS}
    probe_tasks = [
        _probe_llm_backend(name, cfg.url, cfg.model_id) for name, cfg in llm_cfgs.items()
    ]
    try:
        backends: list[LLMBackendStatus] = await asyncio.gather(*probe_tasks)
    except Exception:
        backends = []

    # Cron job descriptions
    cron_descriptions = [
        f"{cj.name.__name__} every {cj.minute or '*'}m/{cj.hour or '*'}h"
        for cj in getattr(WorkerSettings, "cron_jobs", [])
    ]

    debug_enabled = await store.get(_SK_OBS_DEBUG)
    if debug_enabled is None:
        debug_enabled = app_settings.debug_enabled

    return SystemInfoOut(
        app_version=os.getenv("APP_VERSION", "dev"),
        python_version=sys.version.split()[0],
        db_host=db_host,
        db_port=db_port,
        db_name=db_name,
        db_ssl_mode=db_ssl,
        redis_url_host=redis_host,
        llm_backends=list(backends),
        cognitive_tasks=sorted(COGNITIVE_TASKS.keys()),
        cron_jobs=cron_descriptions,
        debug_enabled=bool(debug_enabled),
    )


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------


def _validate_uuid(value: str) -> None:
    """Raise 400 if value is not a valid UUID — prevents SQL injection via path params."""
    try:
        uuid.UUID(value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid UUID format") from exc
