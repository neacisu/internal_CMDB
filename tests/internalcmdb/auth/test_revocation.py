"""Tests for internalcmdb.auth.revocation."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest


def _future(seconds: int = 300) -> datetime:
    return datetime.now(UTC) + timedelta(seconds=seconds)


def _past(seconds: int = 5) -> datetime:
    return datetime.now(UTC) - timedelta(seconds=seconds)


# ---------------------------------------------------------------------------
# revoke_token
# ---------------------------------------------------------------------------


def test_revoke_token_calls_setex() -> None:
    redis = MagicMock()
    with patch("internalcmdb.auth.revocation._redis_client", return_value=redis):
        from internalcmdb.auth.revocation import revoke_token  # noqa: PLC0415

        revoke_token("jti-1", _future(300))
        redis.setex.assert_called_once()
        key, ttl, val = redis.setex.call_args[0]
        assert "jti-1" in key
        assert ttl > 0
        assert val == "1"


def test_revoke_token_skips_already_expired() -> None:
    redis = MagicMock()
    with patch("internalcmdb.auth.revocation._redis_client", return_value=redis):
        from internalcmdb.auth.revocation import revoke_token  # noqa: PLC0415

        revoke_token("jti-expired", _past(10))
        redis.setex.assert_not_called()


def test_revoke_token_logs_warning_when_redis_unavailable(caplog: pytest.LogCaptureFixture) -> None:
    with patch("internalcmdb.auth.revocation._redis_client", return_value=None):
        from internalcmdb.auth.revocation import revoke_token  # noqa: PLC0415

        with caplog.at_level(logging.WARNING, logger="internalcmdb.auth.revocation"):
            revoke_token("jti-noop", _future())
    assert "unavailable" in caplog.text.lower()


# ---------------------------------------------------------------------------
# is_revoked
# ---------------------------------------------------------------------------


def test_is_revoked_returns_true_when_key_exists() -> None:
    redis = MagicMock()
    redis.exists.return_value = 1
    with patch("internalcmdb.auth.revocation._redis_client", return_value=redis):
        from internalcmdb.auth.revocation import is_revoked  # noqa: PLC0415

        assert is_revoked("jti-revoked") is True


def test_is_revoked_returns_false_when_key_absent() -> None:
    redis = MagicMock()
    redis.exists.return_value = 0
    with patch("internalcmdb.auth.revocation._redis_client", return_value=redis):
        from internalcmdb.auth.revocation import is_revoked  # noqa: PLC0415

        assert is_revoked("jti-fresh") is False


def test_is_revoked_fail_open_when_redis_unavailable() -> None:
    with patch("internalcmdb.auth.revocation._redis_client", return_value=None):
        from internalcmdb.auth.revocation import is_revoked  # noqa: PLC0415

        assert is_revoked("any-jti") is False


def test_is_revoked_fail_open_on_redis_error() -> None:
    redis = MagicMock()
    redis.exists.side_effect = Exception("connection reset")
    with patch("internalcmdb.auth.revocation._redis_client", return_value=redis):
        from internalcmdb.auth.revocation import is_revoked  # noqa: PLC0415

        assert is_revoked("jti-error") is False
