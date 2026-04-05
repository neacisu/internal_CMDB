"""Settings API schemas — DTOs for all /settings endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import AnyHttpUrl, field_validator, model_validator

from internalcmdb.api.schemas.common import OrmBase

# Accepted URL schemes for all endpoint URL fields (OWASP A03 — prevent non-HTTP injection)
_HTTP_SCHEMES: tuple[str, str] = ("http://", "https://")


# ---------------------------------------------------------------------------
# Generic app_setting DTOs
# ---------------------------------------------------------------------------

class AppSettingOut(OrmBase):
    """Public representation of a single config.app_setting row."""

    setting_key: str
    setting_group: str
    value: Any
    default: Any
    type_hint: str
    description: str | None = None
    is_secret: bool
    requires_restart: bool
    updated_at: datetime | None = None
    updated_by: str | None = None

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> AppSettingOut:
        return cls(
            setting_key=row["setting_key"],
            setting_group=row["setting_group"],
            value=row["value_jsonb"],
            default=row["default_jsonb"],
            type_hint=row["type_hint"],
            description=row.get("description"),
            is_secret=row.get("is_secret", False),
            requires_restart=row.get("requires_restart", False),
            updated_at=row.get("updated_at"),
            updated_by=row.get("updated_by"),
        )


class AppSettingUpdate(OrmBase):
    """Request body for PUT /settings/{key}."""

    value: Any


class SettingGroupOut(OrmBase):
    """All settings for one group."""

    group: str
    settings: list[AppSettingOut]


# ---------------------------------------------------------------------------
# LLM configuration
# ---------------------------------------------------------------------------

class LLMModelConfig(OrmBase):
    """Config for a single LLM backend."""

    url: str
    model_id: str
    timeout_s: int


class LLMConfigOut(OrmBase):
    """Full LLM layer configuration."""

    reasoning: LLMModelConfig
    fast: LLMModelConfig
    embed: LLMModelConfig
    guard: LLMModelConfig
    guard_token_set: bool          # True when llm.guard.token is non-empty
    circuit_breaker_threshold: int
    circuit_breaker_cooldown_s: int
    max_connections: int
    max_keepalive: int
    max_retries: int


class LLMConfigUpdate(OrmBase):
    """Request body for PUT /settings/llm."""

    reasoning_url: str | None = None
    fast_url: str | None = None
    embed_url: str | None = None
    guard_url: str | None = None
    reasoning_model_id: str | None = None
    fast_model_id: str | None = None
    embed_model_id: str | None = None
    reasoning_timeout_s: int | None = None
    fast_timeout_s: int | None = None
    embed_timeout_s: int | None = None
    guard_timeout_s: int | None = None
    guard_token: str | None = None
    circuit_breaker_threshold: int | None = None
    circuit_breaker_cooldown_s: int | None = None
    max_connections: int | None = None
    max_keepalive: int | None = None
    max_retries: int | None = None

    @field_validator("reasoning_url", "fast_url", "embed_url", "guard_url", mode="before")
    @classmethod
    def _validate_url(cls, v: Any) -> Any:
        if v is None:
            return v
        url_str = str(v)
        if not url_str.startswith(_HTTP_SCHEMES):
            raise ValueError(f"URL must start with http:// or https://, got: {url_str!r}")
        return url_str


# ---------------------------------------------------------------------------
# Token budgets
# ---------------------------------------------------------------------------

class TokenBudgetConfig(OrmBase):
    """Per-caller token budget entry."""

    caller: str
    tokens_per_hour: int
    spike_multiplier: float


class TokenBudgetUpdate(OrmBase):
    """Update a single caller's hourly token budget."""

    tokens_per_hour: int

    @field_validator("tokens_per_hour")
    @classmethod
    def _positive(cls, v: int) -> int:
        if v < 1000:
            raise ValueError("tokens_per_hour must be at least 1000")
        return v


# ---------------------------------------------------------------------------
# Guard & safety
# ---------------------------------------------------------------------------

_ALLOWED_TOOL_CALLS: frozenset[str] = frozenset({
    "query_registry", "list_hosts", "list_services", "get_host_facts",
    "get_service_instances", "search_documents", "get_health_score",
    "list_insights", "generate_report", "check_drift",
    "run_collector", "list_evidence_packs",
})


class GuardConfig(OrmBase):
    """Guard pipeline and LLM safety configuration."""

    fail_closed: bool
    guard_url: str
    timeout_s: float
    tool_allowlist: list[str]
    max_actions_per_session: dict[str, int]


class GuardConfigUpdate(OrmBase):
    fail_closed: bool | None = None
    timeout_s: float | None = None

    @field_validator("timeout_s")
    @classmethod
    def _positive(cls, v: float | None) -> float | None:
        if v is not None and v <= 0:
            raise ValueError("timeout_s must be positive")
        return v


# ---------------------------------------------------------------------------
# HITL governance
# ---------------------------------------------------------------------------

class HITLConfig(OrmBase):
    """HITL escalation thresholds and limits."""

    rc4_escalation_minutes: int
    rc3_escalation_minutes: int
    rc2_escalation_hours: int
    max_escalations: int


class HITLConfigUpdate(OrmBase):
    rc4_escalation_minutes: int | None = None
    rc3_escalation_minutes: int | None = None
    rc2_escalation_hours: int | None = None
    max_escalations: int | None = None

    @model_validator(mode="after")
    def _positive_values(self) -> HITLConfigUpdate:
        for field_name in ("rc4_escalation_minutes", "rc3_escalation_minutes",
                           "rc2_escalation_hours", "max_escalations"):
            val = getattr(self, field_name)
            if val is not None and val < 1:
                raise ValueError(f"{field_name} must be at least 1")
        return self


# ---------------------------------------------------------------------------
# Self-heal
# ---------------------------------------------------------------------------

class SelfHealConfig(OrmBase):
    """Self-healing thresholds for disk and container log management."""

    disk_threshold_pct: int
    log_auto_truncate_bytes: int
    log_hitl_bytes: int


class SelfHealConfigUpdate(OrmBase):
    disk_threshold_pct: int | None = None
    log_auto_truncate_bytes: int | None = None
    log_hitl_bytes: int | None = None

    @field_validator("disk_threshold_pct")
    @classmethod
    def _disk_range(cls, v: int | None) -> int | None:
        if v is not None and not (50 <= v <= 99):
            raise ValueError("disk_threshold_pct must be between 50 and 99")
        return v

    @model_validator(mode="after")
    def _log_order(self) -> SelfHealConfigUpdate:
        auto = self.log_auto_truncate_bytes
        hitl = self.log_hitl_bytes
        if auto is not None and hitl is not None and hitl >= auto:
            raise ValueError(
                "log_hitl_bytes must be less than log_auto_truncate_bytes"
            )
        return self


# ---------------------------------------------------------------------------
# Retention
# ---------------------------------------------------------------------------

class RetentionConfig(OrmBase):
    """Per-table data retention windows (days)."""

    job_history_days: int
    audit_events_days: int
    snapshots_days: int
    llm_calls_days: int
    metric_points_days: int
    insights_days: int


class RetentionConfigUpdate(OrmBase):
    job_history_days: int | None = None
    audit_events_days: int | None = None
    snapshots_days: int | None = None
    llm_calls_days: int | None = None
    metric_points_days: int | None = None
    insights_days: int | None = None

    @model_validator(mode="after")
    def _days_range(self) -> RetentionConfigUpdate:
        for field_name in type(self).model_fields:
            val = getattr(self, field_name)
            if val is not None and not (7 <= val <= 1825):
                raise ValueError(f"{field_name} must be between 7 and 1825 days")
        return self


# ---------------------------------------------------------------------------
# Observability
# ---------------------------------------------------------------------------

class ObservabilityConfig(OrmBase):
    """OTLP, logging, and application runtime configuration."""

    otlp_endpoint: str
    otlp_protocol: str
    otlp_insecure: bool
    sample_rate: float
    log_level: str
    debug_enabled: bool
    cors_origins: list[str]


class ObservabilityConfigUpdate(OrmBase):
    otlp_endpoint: str | None = None
    otlp_protocol: str | None = None
    otlp_insecure: bool | None = None
    sample_rate: float | None = None
    log_level: str | None = None
    debug_enabled: bool | None = None
    cors_origins: list[str] | None = None

    @field_validator("otlp_endpoint", mode="before")
    @classmethod
    def _url(cls, v: Any) -> Any:
        if v is None:
            return v
        url_str = str(v)
        if not url_str.startswith(_HTTP_SCHEMES):
            raise ValueError("otlp_endpoint must start with http:// or https://")
        return url_str

    @field_validator("otlp_protocol")
    @classmethod
    def _protocol(cls, v: str | None) -> str | None:
        if v is not None and v not in ("grpc", "http"):
            raise ValueError("otlp_protocol must be 'grpc' or 'http'")
        return v

    @field_validator("log_level")
    @classmethod
    def _log_level(cls, v: str | None) -> str | None:
        if v is not None and v.upper() not in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
            raise ValueError("log_level must be DEBUG, INFO, WARNING, ERROR, or CRITICAL")
        return v.upper() if v else v

    @field_validator("sample_rate")
    @classmethod
    def _rate(cls, v: float | None) -> float | None:
        if v is not None and not (0.0 <= v <= 1.0):
            raise ValueError("sample_rate must be between 0.0 and 1.0")
        return v


# ---------------------------------------------------------------------------
# Notification channels
# ---------------------------------------------------------------------------

class NotificationChannelOut(OrmBase):
    """Public representation of a notification channel (no secret)."""

    channel_id: str
    name: str
    channel_type: str
    target_url: str | None = None
    events: list[str]
    is_active: bool
    hmac_configured: bool        # True when hmac_secret_hash is set
    created_at: datetime | None = None
    updated_at: datetime | None = None


class NotificationChannelCreate(OrmBase):
    """Create a new notification channel."""

    name: str
    target_url: str
    hmac_secret: str | None = None     # stored as SHA-256 hash, never returned
    events: list[str]
    is_active: bool = True

    @field_validator("target_url", mode="before")
    @classmethod
    def _url(cls, v: Any) -> Any:
        url_str = str(v)
        if not url_str.startswith(_HTTP_SCHEMES):
            raise ValueError("target_url must start with http:// or https://")
        return url_str

    @field_validator("events")
    @classmethod
    def _events_not_empty(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("At least one event type must be selected")
        return v


class NotificationChannelUpdate(OrmBase):
    """Update an existing notification channel."""

    name: str | None = None
    target_url: str | None = None
    hmac_secret: str | None = None
    events: list[str] | None = None
    is_active: bool | None = None

    @field_validator("target_url", mode="before")
    @classmethod
    def _url(cls, v: Any) -> Any:
        if v is None:
            return v
        url_str = str(v)
        if not url_str.startswith(_HTTP_SCHEMES):
            raise ValueError("target_url must start with http:// or https://")
        return url_str


class TestNotificationResult(OrmBase):
    """Result of a test notification send."""

    success: bool
    status_code: int | None = None
    error: str | None = None
    latency_ms: int | None = None


# ---------------------------------------------------------------------------
# User preferences
# ---------------------------------------------------------------------------

class UserPreferenceOut(OrmBase):
    """A single user preference entry."""

    preference_key: str
    value: Any
    updated_at: datetime | None = None


class UserPreferenceUpdate(OrmBase):
    """Set or update a preference value."""

    value: Any


# ---------------------------------------------------------------------------
# System info
# ---------------------------------------------------------------------------

class LLMBackendStatus(OrmBase):
    """Live health status for one LLM backend."""

    name: str
    model: str
    url: str
    reachable: bool
    response_ms: int | None = None
    error: str | None = None


class SystemInfoOut(OrmBase):
    """Read-only system information panel."""

    app_version: str
    python_version: str
    db_host: str
    db_port: int
    db_name: str
    db_ssl_mode: str
    redis_url_host: str            # host:port only, no credentials
    llm_backends: list[LLMBackendStatus]
    cognitive_tasks: list[str]
    cron_jobs: list[str]
    debug_enabled: bool
