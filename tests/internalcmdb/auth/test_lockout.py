"""Tests for internalcmdb.auth.lockout."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from starlette.requests import Request as StarletteRequest

from internalcmdb.auth.lockout import get_client_ip

# ---------------------------------------------------------------------------
# Test-fixture IP addresses — non-routable ranges, no production meaning.
# Hardcoded literals are intentional test fixtures (S1313 acknowledged).
# ---------------------------------------------------------------------------
_TEST_CLIENT_IP: str = "1.2.3.4"  # NOSONAR
_TEST_FORWARDED_IP: str = "10.0.0.1"  # NOSONAR
_TEST_FORWARDED_CHAIN: str = f"{_TEST_FORWARDED_IP}, 172.16.0.1"


def _make_request(
    forwarded: str | None = None,
    client_host: str = _TEST_CLIENT_IP,
) -> StarletteRequest:
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/v1/auth/login",
        "query_string": b"",
        "headers": [(b"x-forwarded-for", forwarded.encode())] if forwarded else [],
        "client": (client_host, 12345),
    }
    return StarletteRequest(scope)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# _get_client_ip
# ---------------------------------------------------------------------------


def test_get_client_ip_uses_forwarded_for() -> None:
    req = _make_request(forwarded=_TEST_FORWARDED_CHAIN)
    assert get_client_ip(req) == _TEST_FORWARDED_IP


def test_get_client_ip_falls_back_to_client_host() -> None:
    req = _make_request()
    assert get_client_ip(req) == _TEST_CLIENT_IP


# ---------------------------------------------------------------------------
# record_failed_attempt
# ---------------------------------------------------------------------------


def test_record_failed_attempt_increments_key() -> None:
    redis = MagicMock()
    redis.incr.return_value = 2
    with patch("internalcmdb.auth.lockout._redis_client", return_value=redis):
        from internalcmdb.auth.lockout import record_failed_attempt  # noqa: PLC0415

        count = record_failed_attempt(_TEST_CLIENT_IP, "alice@example.com")
    assert count == 2
    redis.incr.assert_called_once()
    redis.expire.assert_called_once()


def test_record_failed_attempt_returns_zero_when_redis_unavailable() -> None:
    with patch("internalcmdb.auth.lockout._redis_client", return_value=None):
        from internalcmdb.auth.lockout import record_failed_attempt  # noqa: PLC0415

        assert record_failed_attempt(_TEST_CLIENT_IP, "alice@example.com") == 0


# ---------------------------------------------------------------------------
# is_locked_out
# ---------------------------------------------------------------------------


def test_is_locked_out_true_when_threshold_reached() -> None:
    redis = MagicMock()
    redis.get.return_value = "5"
    with patch("internalcmdb.auth.lockout._redis_client", return_value=redis):
        from internalcmdb.auth.lockout import is_locked_out  # noqa: PLC0415

        assert is_locked_out(_TEST_CLIENT_IP, "alice@example.com") is True


def test_is_locked_out_false_below_threshold() -> None:
    redis = MagicMock()
    redis.get.return_value = "3"
    with patch("internalcmdb.auth.lockout._redis_client", return_value=redis):
        from internalcmdb.auth.lockout import is_locked_out  # noqa: PLC0415

        assert is_locked_out(_TEST_CLIENT_IP, "alice@example.com") is False


def test_is_locked_out_false_when_key_absent() -> None:
    redis = MagicMock()
    redis.get.return_value = None
    with patch("internalcmdb.auth.lockout._redis_client", return_value=redis):
        from internalcmdb.auth.lockout import is_locked_out  # noqa: PLC0415

        assert is_locked_out(_TEST_CLIENT_IP, "alice@example.com") is False


def test_is_locked_out_fail_open_when_redis_unavailable() -> None:
    with patch("internalcmdb.auth.lockout._redis_client", return_value=None):
        from internalcmdb.auth.lockout import is_locked_out  # noqa: PLC0415

        assert is_locked_out(_TEST_CLIENT_IP, "alice@example.com") is False


# ---------------------------------------------------------------------------
# clear_lockout
# ---------------------------------------------------------------------------


def test_clear_lockout_deletes_key() -> None:
    redis = MagicMock()
    with patch("internalcmdb.auth.lockout._redis_client", return_value=redis):
        from internalcmdb.auth.lockout import clear_lockout  # noqa: PLC0415

        clear_lockout(_TEST_CLIENT_IP, "alice@example.com")
    redis.delete.assert_called_once()
