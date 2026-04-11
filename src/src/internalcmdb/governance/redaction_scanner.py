"""internalCMDB — Ingest-Time Redaction Scanner (pt-056).

Scans ``ObservedFact`` content payloads for credential patterns before they
are persisted.  Any fact whose ``fact_value_jsonb`` or serialised text
representation matches a known credential pattern is **rejected** — it is NOT
written to ``discovery.observed_fact``.

Rejection events are recorded in the ``CollectionRun.summary_jsonb`` under key
``"redaction_rejections"`` so that the run record is always auditable.

Public surface::

    from internalcmdb.governance.redaction_scanner import RedactionScanner

    scanner = RedactionScanner()
    result = scanner.scan_fact_payload(candidate_jsonb)
    if not result.safe:
        # Reject — do not write the fact
        scanner.record_rejection(collection_run, candidate_label, result)
    else:
        # Safe to persist
        session.add(ObservedFact(..., fact_value_jsonb=candidate_jsonb))
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from internalcmdb.models.discovery import CollectionRun

# ---------------------------------------------------------------------------
# Credential patterns — each tuple is (label, compiled regex)
# ---------------------------------------------------------------------------

_CREDENTIAL_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    # Generic password assignments
    ("password_assignment", re.compile(r"(?i)password\s*[:=]\s*\S{4,}", re.IGNORECASE)),
    # API keys and tokens
    ("api_key_assignment", re.compile(r"(?i)(api[_-]?key|token)\s*[:=]\s*\S{8,}", re.IGNORECASE)),
    # Private key header (PEM)
    ("pem_private_key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    # HuggingFace tokens
    ("huggingface_token", re.compile(r"hf_[A-Za-z0-9]{20,}")),
    # Connection strings with embedded credentials
    (
        "connection_string_with_creds",
        re.compile(r"(?i)(postgres|mysql|mongodb|redis)://[^:@\s]+:[^@\s]+@"),
    ),
    # AWS access key IDs
    ("aws_access_key", re.compile(r"AKIA[0-9A-Z]{16}")),
    # Generic secret assignments
    ("secret_assignment", re.compile(r"(?i)secret\s*[:=]\s*\S{8,}", re.IGNORECASE)),
]


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ScanResult:
    """Outcome of scanning a single fact payload."""

    safe: bool
    matched_patterns: tuple[str, ...] = field(default_factory=tuple)

    def __init__(self, *, safe: bool, matched_patterns: list[str] | None = None) -> None:
        object.__setattr__(self, "safe", safe)
        object.__setattr__(self, "matched_patterns", tuple(matched_patterns or []))


# ---------------------------------------------------------------------------
# Scanner
# ---------------------------------------------------------------------------


class RedactionScanner:
    """Checks JSONB payloads for credential patterns before fact ingestion."""

    def scan_fact_payload(self, payload: dict[str, Any] | None) -> ScanResult:
        """Scan a ``fact_value_jsonb`` dict for credential patterns.

        Returns a :class:`ScanResult` with ``safe=True`` when no patterns
        matched, and ``safe=False`` plus the matched pattern labels otherwise.
        """
        if payload is None:
            return ScanResult(safe=True)

        text = _jsonb_to_text(payload)
        matched: list[str] = []
        for label, pattern in _CREDENTIAL_PATTERNS:
            if pattern.search(text):
                matched.append(label)

        return ScanResult(safe=(not matched), matched_patterns=matched if matched else None)

    def record_rejection(
        self,
        run: CollectionRun,
        candidate_label: str,
        result: ScanResult,
    ) -> None:
        """Append a rejection entry to the ``CollectionRun.summary_jsonb``.

        This ensures that every rejection is permanently recorded in the run
        record and is auditable without the rejected payload ever being stored.
        """
        summary: dict[str, Any] = dict(run.summary_jsonb or {})
        rejections: list[dict[str, Any]] = list(summary.get("redaction_rejections", []))
        rejections.append(
            {
                "candidate_label": candidate_label,
                "matched_patterns": list(result.matched_patterns),
            }
        )
        summary["redaction_rejections"] = rejections
        run.summary_jsonb = summary


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _jsonb_to_text(payload: dict[str, Any]) -> str:
    """Convert a JSONB payload to a flat text string for pattern matching."""
    return json.dumps(payload, ensure_ascii=False)
