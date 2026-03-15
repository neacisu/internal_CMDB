"""Tests for internalcmdb.governance.redaction_scanner (pt-056).

Covers:
- All 7 credential patterns trigger a denial (safe=False, matched_patterns non-empty)
- Clean payloads produce safe=True
- None payload is safe
- Mixed payload flags only the matching patterns
- record_rejection mutates run.summary_jsonb correctly
"""

from __future__ import annotations

# pylint: disable=redefined-outer-name
from unittest.mock import MagicMock

import pytest

from internalcmdb.governance.redaction_scanner import (  # pylint: disable=import-error
    RedactionScanner,
    ScanResult,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def scanner() -> RedactionScanner:
    return RedactionScanner()


def _make_run() -> MagicMock:
    """Stub with a mutable summary_jsonb dict (like an ORM row)."""
    run = MagicMock()
    run.summary_jsonb = {}
    return run


# ---------------------------------------------------------------------------
# Safe payloads
# ---------------------------------------------------------------------------


class TestSafePayloads:
    def test_none_is_safe(self, scanner: RedactionScanner) -> None:
        result = scanner.scan_fact_payload(None)
        assert result.safe is True
        assert not result.matched_patterns

    def test_empty_dict_is_safe(self, scanner: RedactionScanner) -> None:
        result = scanner.scan_fact_payload({})
        assert result.safe is True

    def test_benign_payload_is_safe(self, scanner: RedactionScanner) -> None:
        result = scanner.scan_fact_payload({"hostname": "web-01", "port": "8080"})
        assert result.safe is True
        assert not result.matched_patterns

    def test_clean_description_is_safe(self, scanner: RedactionScanner) -> None:
        result = scanner.scan_fact_payload({"description": "This service runs on port 443"})
        assert result.safe is True


# ---------------------------------------------------------------------------
# Pattern: password_assignment
# ---------------------------------------------------------------------------


class TestPasswordPattern:
    def test_password_equals_triggers(self, scanner: RedactionScanner) -> None:
        result = scanner.scan_fact_payload({"config": "password=s3cr3t_value"})
        assert result.safe is False
        assert "password_assignment" in result.matched_patterns

    def test_password_colon_triggers(self, scanner: RedactionScanner) -> None:
        result = scanner.scan_fact_payload({"config": "password: mysecretpassword"})
        assert result.safe is False
        assert "password_assignment" in result.matched_patterns

    def test_passwd_variation_triggers(self, scanner: RedactionScanner) -> None:
        result = scanner.scan_fact_payload({"auth": "password=hunter2very"})
        assert result.safe is False

    def test_password_word_in_domain_safe(self, scanner: RedactionScanner) -> None:
        # "password policy" or "password complexity" — no value assignment should be safe
        result = scanner.scan_fact_payload({"topic": "The password policy requirements"})
        assert result.safe is True


# ---------------------------------------------------------------------------
# Pattern: api_key_assignment
# ---------------------------------------------------------------------------


class TestApiKeyPattern:
    def test_api_key_equals_triggers(self, scanner: RedactionScanner) -> None:
        fake_key = "api_key=abcdef1234567890abcdef"  # gitleaks:allow
        result = scanner.scan_fact_payload({"auth": fake_key})
        assert result.safe is False
        assert "api_key_assignment" in result.matched_patterns

    def test_apikey_colon_triggers(self, scanner: RedactionScanner) -> None:
        fake_key = "apikey: LIVE_12345678901234567890"  # gitleaks:allow
        result = scanner.scan_fact_payload({"cfg": fake_key})
        assert result.safe is False
        assert "api_key_assignment" in result.matched_patterns


# ---------------------------------------------------------------------------
# Pattern: pem_private_key
# ---------------------------------------------------------------------------


class TestPemPattern:
    def test_pem_rsa_triggers(self, scanner: RedactionScanner) -> None:
        result = scanner.scan_fact_payload({"key": "-----BEGIN RSA PRIVATE KEY-----"})
        assert result.safe is False
        assert "pem_private_key" in result.matched_patterns

    def test_pem_ec_triggers(self, scanner: RedactionScanner) -> None:
        result = scanner.scan_fact_payload({"key": "-----BEGIN EC PRIVATE KEY-----"})
        assert result.safe is False
        assert "pem_private_key" in result.matched_patterns

    def test_pem_generic_triggers(self, scanner: RedactionScanner) -> None:
        result = scanner.scan_fact_payload({"key": "-----BEGIN PRIVATE KEY-----"})
        assert result.safe is False
        assert "pem_private_key" in result.matched_patterns


# ---------------------------------------------------------------------------
# Pattern: huggingface_token
# ---------------------------------------------------------------------------


class TestHuggingFacePattern:
    def test_hf_token_triggers(self, scanner: RedactionScanner) -> None:
        # hf_ followed by 20+ alphanumeric chars
        result = scanner.scan_fact_payload({"token": "hf_ABCDEFGHIJKLMNOPQRSTUVWXYZabcd"})
        assert result.safe is False
        assert "huggingface_token" in result.matched_patterns

    def test_short_hf_prefix_safe(self, scanner: RedactionScanner) -> None:
        # hf_ followed by fewer than 20 chars should NOT match
        result = scanner.scan_fact_payload({"val": "hf_short"})
        assert result.safe is True


# ---------------------------------------------------------------------------
# Pattern: connection_string_with_creds
# ---------------------------------------------------------------------------


class TestConnectionStringPattern:
    def test_postgres_creds_triggers(self, scanner: RedactionScanner) -> None:
        result = scanner.scan_fact_payload({"dsn": "postgres://admin:mypassword@db.host:5432/mydb"})
        assert result.safe is False
        assert "connection_string_with_creds" in result.matched_patterns

    def test_mysql_creds_triggers(self, scanner: RedactionScanner) -> None:
        result = scanner.scan_fact_payload({"url": "mysql://root:password@localhost/mydb"})
        assert result.safe is False
        assert "connection_string_with_creds" in result.matched_patterns

    def test_mongodb_creds_triggers(self, scanner: RedactionScanner) -> None:
        result = scanner.scan_fact_payload({"conn": "mongodb://user:pass@mongo:27017/admin"})
        assert result.safe is False
        assert "connection_string_with_creds" in result.matched_patterns

    def test_conn_without_creds_safe(self, scanner: RedactionScanner) -> None:
        # No user:pass@ in the URL
        result = scanner.scan_fact_payload({"url": "postgresql://db.host:5432/mydb"})
        assert result.safe is True


# ---------------------------------------------------------------------------
# Pattern: aws_access_key
# ---------------------------------------------------------------------------


class TestAwsAccessKeyPattern:
    def test_akia_triggers(self, scanner: RedactionScanner) -> None:
        result = scanner.scan_fact_payload({"key": "AKIAIOSFODNN7EXAMPLE1234"})
        assert result.safe is False
        assert "aws_access_key" in result.matched_patterns

    def test_akia_too_short_safe(self, scanner: RedactionScanner) -> None:
        # AKIA + fewer than 16 chars
        result = scanner.scan_fact_payload({"k": "AKIAIOSFOD"})
        assert result.safe is True


# ---------------------------------------------------------------------------
# Pattern: secret_assignment
# ---------------------------------------------------------------------------


class TestSecretPattern:
    def test_secret_colon_triggers(self, scanner: RedactionScanner) -> None:
        result = scanner.scan_fact_payload({"cfg": "secret: supersecretvalue"})
        assert result.safe is False
        assert "secret_assignment" in result.matched_patterns

    def test_secret_key_equals_triggers(self, scanner: RedactionScanner) -> None:
        result = scanner.scan_fact_payload({"env": "secret=abcdef1234567890"})  # gitleaks:allow
        assert result.safe is False


# ---------------------------------------------------------------------------
# Multiple patterns in one payload
# ---------------------------------------------------------------------------


class TestMultiplePatterns:
    def test_two_patterns_both_reported(self, scanner: RedactionScanner) -> None:
        payload = {
            "key": "AKIAIOSFODNN7EXAMPLE1234",
            "token": "hf_ABCDEFGHIJKLMNOPQRSTUVWXYZabcd",
        }
        result = scanner.scan_fact_payload(payload)
        assert result.safe is False
        assert "aws_access_key" in result.matched_patterns
        assert "huggingface_token" in result.matched_patterns


# ---------------------------------------------------------------------------
# ScanResult is immutable
# ---------------------------------------------------------------------------


class TestScanResultImmutability:
    def test_safe_result_frozen(self) -> None:
        r = ScanResult(safe=True)
        with pytest.raises((AttributeError, TypeError)):
            r.safe = False  # type: ignore[misc]

    def test_unsafe_result_frozen(self) -> None:
        r = ScanResult(safe=False, matched_patterns=["password_assignment"])
        with pytest.raises((AttributeError, TypeError)):
            r.matched_patterns = ("replaced",)  # type: ignore[misc]


# ---------------------------------------------------------------------------
# record_rejection
# ---------------------------------------------------------------------------


class TestRecordRejection:
    def test_record_rejection_populates_summary(self, scanner: RedactionScanner) -> None:
        run = _make_run()
        result = ScanResult(safe=False, matched_patterns=["aws_access_key"])
        scanner.record_rejection(run, "host-fact-001", result)
        assert "redaction_rejections" in run.summary_jsonb

    def test_record_rejection_includes_label(self, scanner: RedactionScanner) -> None:
        run = _make_run()
        result = ScanResult(safe=False, matched_patterns=["pem_private_key"])
        scanner.record_rejection(run, "secret-fact", result)
        rejections = run.summary_jsonb["redaction_rejections"]
        labels = [r["candidate_label"] for r in rejections]
        assert any("secret-fact" in lbl for lbl in labels)

    def test_record_rejection_accumulates_multiple(self, scanner: RedactionScanner) -> None:
        run = _make_run()
        for candidate_label in ("fact-a", "fact-b"):
            result = ScanResult(safe=False, matched_patterns=["password_assignment"])
            scanner.record_rejection(run, candidate_label, result)
        rejections = run.summary_jsonb["redaction_rejections"]
        assert len(rejections) == 2
