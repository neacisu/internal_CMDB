"""Tests for api.schemas.settings — validator logic."""

from __future__ import annotations

import datetime
from typing import Any

import pytest

from internalcmdb.api.schemas.settings import (
    AppSettingOut,
    HITLConfigUpdate,
    LLMConfigUpdate,
    NotificationChannelCreate,
    ObservabilityConfigUpdate,
    RetentionConfigUpdate,
    SelfHealConfigUpdate,
    TokenBudgetUpdate,
    UserPreferenceUpdate,
)

# ---------------------------------------------------------------------------
# AppSettingOut.from_row
# ---------------------------------------------------------------------------


def _base_row(**kwargs: Any) -> dict[str, Any]:
    base = {
        "setting_key": "llm.url",
        "setting_group": "llm",
        "value_jsonb": "http://localhost",
        "default_jsonb": "http://localhost",
        "type_hint": "string",
        "description": "test",
        "is_secret": False,
        "requires_restart": False,
        "updated_at": None,
        "updated_by": None,
    }
    base.update(kwargs)
    return base


def test_app_setting_out_from_row_basic() -> None:
    out = AppSettingOut.from_row(_base_row())
    assert out.setting_key == "llm.url"
    assert out.value == "http://localhost"
    assert out.is_secret is False


def test_app_setting_out_from_row_with_timestamp() -> None:
    ts = datetime.datetime(2024, 1, 1, tzinfo=datetime.UTC)
    out = AppSettingOut.from_row(_base_row(updated_at=ts, updated_by="admin"))
    assert out.updated_by == "admin"


# ---------------------------------------------------------------------------
# LLMConfigUpdate — URL validation (OWASP A03)
# ---------------------------------------------------------------------------


def test_llm_config_update_valid_http_url() -> None:
    u = LLMConfigUpdate(reasoning_url="http://10.0.1.10:49001")
    assert u.reasoning_url == "http://10.0.1.10:49001"


def test_llm_config_update_valid_https_url() -> None:
    u = LLMConfigUpdate(guard_url="https://llm-guard.example.com")
    assert u.guard_url == "https://llm-guard.example.com"


def test_llm_config_update_rejects_javascript_url() -> None:
    with pytest.raises(ValueError, match="http"):
        LLMConfigUpdate(reasoning_url="javascript:alert(1)")


def test_llm_config_update_rejects_file_url() -> None:
    with pytest.raises(ValueError, match="http"):
        LLMConfigUpdate(fast_url="file:///etc/passwd")


def test_llm_config_update_empty_is_ok() -> None:
    """Empty update (no fields set) is valid — allows partial PUT."""
    u = LLMConfigUpdate()
    assert u.reasoning_url is None


# ---------------------------------------------------------------------------
# SelfHealConfigUpdate — log_hitl_bytes < log_auto_truncate_bytes
# ---------------------------------------------------------------------------


def test_self_heal_update_valid() -> None:
    u = SelfHealConfigUpdate(
        log_hitl_bytes=524_288_000,  # 500 MB
        log_auto_truncate_bytes=2_147_483_648,  # 2 GB
    )
    assert u.log_hitl_bytes == 524_288_000


def test_self_heal_update_rejects_when_hitl_gte_auto_truncate() -> None:
    with pytest.raises(ValueError, match="log_hitl_bytes"):
        SelfHealConfigUpdate(
            log_hitl_bytes=2_000_000_000,
            log_auto_truncate_bytes=1_000_000_000,
        )


def test_self_heal_update_partial_ok() -> None:
    """Setting only disk threshold is valid."""
    u = SelfHealConfigUpdate(disk_threshold_pct=80)
    assert u.disk_threshold_pct == 80
    assert u.log_hitl_bytes is None


# ---------------------------------------------------------------------------
# HITLConfigUpdate — all values >= 1
# ---------------------------------------------------------------------------


def test_hitl_update_valid() -> None:
    u = HITLConfigUpdate(rc4_escalation_minutes=15, max_escalations=3)
    assert u.max_escalations == 3


def test_hitl_update_rejects_zero_minutes() -> None:
    with pytest.raises(ValueError, match="at least 1"):
        HITLConfigUpdate(rc4_escalation_minutes=0)


def test_hitl_update_rejects_zero_max_escalations() -> None:
    with pytest.raises(ValueError, match="at least 1"):
        HITLConfigUpdate(max_escalations=0)


# ---------------------------------------------------------------------------
# RetentionConfigUpdate — range 7-1825 days
# ---------------------------------------------------------------------------


def test_retention_update_valid() -> None:
    u = RetentionConfigUpdate(job_history_days=90)
    assert u.job_history_days == 90


def test_retention_update_rejects_below_min() -> None:
    with pytest.raises(ValueError, match="between 7 and 1825"):
        RetentionConfigUpdate(job_history_days=1)


def test_retention_update_rejects_above_max() -> None:
    with pytest.raises(ValueError, match="between 7 and 1825"):
        RetentionConfigUpdate(audit_events_days=9999)


# ---------------------------------------------------------------------------
# ObservabilityConfigUpdate — validators
# ---------------------------------------------------------------------------


def test_observability_update_valid_log_level() -> None:
    u = ObservabilityConfigUpdate(log_level="WARNING")
    assert u.log_level == "WARNING"


def test_observability_update_rejects_invalid_log_level() -> None:
    with pytest.raises(ValueError, match="log_level"):
        ObservabilityConfigUpdate(log_level="VERBOSE")


def test_observability_update_valid_sample_rate() -> None:
    u = ObservabilityConfigUpdate(sample_rate=0.5)
    assert u.sample_rate == pytest.approx(0.5)  # pyright: ignore[reportUnknownMemberType]


def test_observability_update_rejects_negative_sample_rate() -> None:
    with pytest.raises(ValueError, match=r"between 0\.0 and 1\.0"):
        ObservabilityConfigUpdate(sample_rate=-0.1)


def test_observability_update_rejects_sample_rate_above_one() -> None:
    with pytest.raises(ValueError, match=r"between 0\.0 and 1\.0"):
        ObservabilityConfigUpdate(sample_rate=1.1)


def test_observability_update_rejects_invalid_url_scheme() -> None:
    with pytest.raises(ValueError, match="http"):
        ObservabilityConfigUpdate(otlp_endpoint="ftp://oops")


# ---------------------------------------------------------------------------
# NotificationChannelCreate — target_url scheme check
# ---------------------------------------------------------------------------


def test_notification_create_valid_webhook() -> None:
    n = NotificationChannelCreate(
        name="test-hook",
        target_url="https://hooks.example.com/notify",
        events=["insight.created"],
        is_active=True,
    )
    assert n.name == "test-hook"


def test_notification_create_rejects_javascript_url() -> None:
    with pytest.raises(ValueError, match="http"):
        NotificationChannelCreate(
            name="evil",
            target_url="javascript:alert(0)",
            events=[],
            is_active=True,
        )


# ---------------------------------------------------------------------------
# TokenBudgetUpdate
# ---------------------------------------------------------------------------


def test_token_budget_update_minimum_valid() -> None:
    u = TokenBudgetUpdate(tokens_per_hour=1000)
    assert u.tokens_per_hour == 1000


def test_token_budget_update_rejects_zero() -> None:
    with pytest.raises(ValueError, match="at least 1000"):
        TokenBudgetUpdate(tokens_per_hour=0)


# ---------------------------------------------------------------------------
# UserPreferenceUpdate
# ---------------------------------------------------------------------------


def test_user_preference_update_accepts_any_json_value() -> None:
    for val in [True, 42, "str", [1, 2], {"a": 1}]:
        u = UserPreferenceUpdate(value=val)
        assert u.value == val
