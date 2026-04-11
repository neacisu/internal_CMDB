"""Integrations router — external service configuration and webhooks.

Currently supports:
- TimelinesAI (WhatsApp communication)

Security notes:
  - API tokens stored encrypted via SettingsStore (never returned in GET response)
  - Webhook payloads validated by HMAC-SHA256 when secret is configured (OWASP A02)
  - All write endpoints require admin role
"""

from __future__ import annotations

import hashlib
import hmac
import logging
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, field_validator

from internalcmdb.api.middleware.rbac import require_role
from internalcmdb.config.settings_store import SettingsStore, get_settings_store

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/integrations", tags=["integrations"])

_READER_ROLES = ("admin", "operator", "viewer")
_ADMIN_ROLES = ("admin",)

_TIMELINESAI_BASE = "https://app.timelines.ai/integrations/api"

# Setting keys
_SK_TAI_ENABLED = "integrations.timelinesai.enabled"
_SK_TAI_TOKEN = "integrations.timelinesai.api_token"
_SK_TAI_WEBHOOK_SECRET = "integrations.timelinesai.webhook_secret"
_SK_TAI_EVENTS = "integrations.timelinesai.subscribed_events"
_SK_TAI_AUTO_REPLY = "integrations.timelinesai.auto_reply_enabled"
_SK_TAI_REPLY_TPL = "integrations.timelinesai.auto_reply_template"


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class TimelinesAIConfig(BaseModel):
    enabled: bool = False
    api_token: str = ""
    webhook_secret: str = ""
    subscribed_events: list[str] = ["message:received:new"]
    auto_reply_enabled: bool = False
    auto_reply_template: str = ""

    @field_validator("subscribed_events")
    @classmethod
    def _validate_events(cls, v: list[str]) -> list[str]:
        allowed = {
            "message:new", "message:received:new", "message:sent:new",
            "chat:created", "chat:received:created", "chat:sent:created",
            "chat:assigned", "chat:unassigned",
        }
        invalid = [e for e in v if e not in allowed]
        if invalid:
            raise ValueError(f"Unknown events: {invalid}")
        return v

    @field_validator("api_token")
    @classmethod
    def _no_whitespace(cls, v: str) -> str:
        return v.strip()


class TimelinesAITestResult(BaseModel):
    ok: bool
    workspace_name: str | None = None
    error: str | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _store() -> SettingsStore:
    return get_settings_store()


async def _load_config(store: SettingsStore) -> TimelinesAIConfig:
    return TimelinesAIConfig(
        enabled=bool(await store.get(_SK_TAI_ENABLED) or False),
        api_token="",  # never return the raw token
        webhook_secret="",  # never return the secret
        subscribed_events=list(await store.get(_SK_TAI_EVENTS) or ["message:received:new"]),
        auto_reply_enabled=bool(await store.get(_SK_TAI_AUTO_REPLY) or False),
        auto_reply_template=str(await store.get(_SK_TAI_REPLY_TPL) or ""),
    )


# ---------------------------------------------------------------------------
# TimelinesAI endpoints
# ---------------------------------------------------------------------------

@router.get(
    "/timelinesai/config",
    response_model=TimelinesAIConfig,
    dependencies=[Depends(require_role(*_READER_ROLES))],
    summary="Get TimelinesAI integration configuration (tokens masked)",
)
async def get_timelinesai_config() -> TimelinesAIConfig:
    store = _store()
    cfg = await _load_config(store)
    # Indicate whether tokens are set (without revealing them)
    token_raw = await store.get(_SK_TAI_TOKEN)
    secret_raw = await store.get(_SK_TAI_WEBHOOK_SECRET)
    cfg.api_token = "***" if token_raw else ""
    cfg.webhook_secret = "***" if secret_raw else ""
    return cfg


@router.put(
    "/timelinesai/config",
    response_model=TimelinesAIConfig,
    dependencies=[Depends(require_role(*_ADMIN_ROLES))],
    summary="Save TimelinesAI integration configuration",
)
async def save_timelinesai_config(body: TimelinesAIConfig) -> TimelinesAIConfig:
    store = _store()
    await store.set(_SK_TAI_ENABLED, body.enabled)
    await store.set(_SK_TAI_EVENTS, body.subscribed_events)
    await store.set(_SK_TAI_AUTO_REPLY, body.auto_reply_enabled)
    await store.set(_SK_TAI_REPLY_TPL, body.auto_reply_template)
    # Only update secrets if they are not the masked placeholder
    if body.api_token and body.api_token != "***":
        await store.set(_SK_TAI_TOKEN, body.api_token)
    if body.webhook_secret and body.webhook_secret != "***":
        await store.set(_SK_TAI_WEBHOOK_SECRET, body.webhook_secret)
    return await _load_config(store)


@router.post(
    "/timelinesai/test",
    response_model=TimelinesAITestResult,
    dependencies=[Depends(require_role(*_READER_ROLES))],
    summary="Test TimelinesAI API connection using stored token",
)
async def test_timelinesai_connection() -> TimelinesAITestResult:
    store = _store()
    token = await store.get(_SK_TAI_TOKEN)
    if not token:
        raise HTTPException(status_code=400, detail="No API token configured")

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(
                f"{_TIMELINESAI_BASE}/whatsapp_accounts",
                headers={"Authorization": f"Bearer {token}"},
            )
        if resp.status_code == status.HTTP_200_OK:
            data: Any = resp.json()
            accounts = data if isinstance(data, list) else data.get("data", [])
            name = accounts[0].get("full_name") if accounts else None
            return TimelinesAITestResult(ok=True, workspace_name=name)
        if resp.status_code == status.HTTP_401_UNAUTHORIZED:
            return TimelinesAITestResult(ok=False, error="Invalid or expired API token")
        return TimelinesAITestResult(ok=False, error=f"API returned {resp.status_code}")
    except httpx.TimeoutException:
        return TimelinesAITestResult(ok=False, error="Connection timeout")
    except httpx.ConnectError as exc:
        return TimelinesAITestResult(ok=False, error=f"ConnectError: {exc}")
    except Exception as exc:
        logger.exception("TimelinesAI test failed")
        return TimelinesAITestResult(ok=False, error=str(exc))


@router.post(
    "/timelinesai/webhook",
    status_code=status.HTTP_200_OK,
    include_in_schema=True,
    summary="Inbound webhook receiver for TimelinesAI events",
)
async def timelinesai_webhook(request: Request) -> dict[str, str]:
    """Accept inbound webhook events from TimelinesAI.

    If a webhook secret is configured, validates the HMAC-SHA256 signature
    in the X-TimelinesAI-Signature header before processing.
    """
    store = _store()
    body = await request.body()

    # HMAC validation when secret is set
    secret = await store.get(_SK_TAI_WEBHOOK_SECRET)
    if secret:
        sig_header = request.headers.get("X-TimelinesAI-Signature", "")
        expected = hmac.new(
            key=str(secret).encode(),
            msg=body,
            digestmod=hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(sig_header, expected):
            raise HTTPException(status_code=401, detail="Invalid webhook signature")

    # Check integration is enabled
    enabled = await store.get(_SK_TAI_ENABLED)
    if not enabled:
        return {"status": "integration_disabled"}

    try:
        import json  # noqa: PLC0415
        payload: dict[str, Any] = json.loads(body)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload") from None

    event_type = payload.get("event_type", "")
    subscribed = list(await store.get(_SK_TAI_EVENTS) or [])

    if event_type not in subscribed:
        return {"status": "event_not_subscribed"}

    # Auto-reply for new incoming messages
    if event_type == "message:received:new":
        auto_reply = await store.get(_SK_TAI_AUTO_REPLY)
        if auto_reply:
            template = str(await store.get(_SK_TAI_REPLY_TPL) or "")
            phone = payload.get("chat", {}).get("phone")
            if phone and template:
                await _send_auto_reply(store, phone, template)

    logger.info("TimelinesAI webhook: event=%s", event_type)
    return {"status": "ok"}


async def _send_auto_reply(store: SettingsStore, phone: str, message: str) -> None:
    token = await store.get(_SK_TAI_TOKEN)
    if not token:
        return
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(
                f"{_TIMELINESAI_BASE}/messages",
                headers={"Authorization": f"Bearer {token}"},
                json={"phone": phone, "message": message},
            )
    except Exception:
        logger.exception("TimelinesAI auto-reply failed for phone=%s", phone)
