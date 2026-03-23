"""F2.2 — Drift Detector: compare observed state against canonical documents.

Performs field-by-field comparison between live-observed infrastructure state
and the canonical (desired) configuration.  Each detected drift is classified
as intentional, accidental, or critical based on the nature of the changed
fields.

Usage::

    from internalcmdb.cognitive.drift_detector import DriftDetector

    detector = DriftDetector()
    result = detector.detect_drift(entity_id, observed, canonical)
    if result.has_drift:
        print(f"{result.drift_type}: {result.fields_changed}")
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Fields whose changes are always classified as security-critical drift.
_CRITICAL_FIELDS: frozenset[str] = frozenset({
    "sshd_config",
    "firewall_rules",
    "iptables",
    "nftables",
    "tls_version",
    "tls_cipher",
    "certificate_fingerprint",
    "certificate_expiry",
    "authorized_keys",
    "root_login",
    "password_auth",
    "port",
    "listen_address",
    "permit_root_login",
    "allowed_users",
    "security_group",
    "selinux_mode",
    "apparmor_profile",
})

# Fields whose changes are typically intentional (planned maintenance).
_INTENTIONAL_FIELDS: frozenset[str] = frozenset({
    "version",
    "image",
    "image_tag",
    "container_image",
    "replicas",
    "resource_limits",
    "resource_requests",
    "environment",
    "labels",
    "annotations",
    "description",
    "metadata",
    "tags",
    "scaling_policy",
})


@dataclass(frozen=True)
class DriftResult:
    """Outcome of a drift detection comparison.

    Attributes:
        has_drift:       True when at least one field differs.
        drift_type:      ``"intentional"`` | ``"accidental"`` | ``"critical"``
                         | ``"missing_canonical"`` | ``"error"``
                         — the highest-severity type among all changed fields.
        fields_changed:  List of field names that differ.
        confidence:      0.0–1.0 confidence in the classification.
        explanation:     Human-readable summary of the drift.
    """

    has_drift: bool
    drift_type: str
    fields_changed: list[str] = field(default_factory=list)
    confidence: float = 1.0
    explanation: str = ""


class DriftDetector:
    """Stateless drift comparator.

    Compares two flat or shallow-nested dictionaries field by field.
    """

    def detect_drift(
        self,
        entity_id: str,
        observed: dict[str, Any] | None,
        canonical: dict[str, Any] | None,
    ) -> DriftResult:
        """Compare *observed* state against *canonical* desired state.

        Args:
            entity_id: Identifier of the entity being compared (for reporting).
            observed:  Dictionary of observed field values (live infrastructure).
            canonical: Dictionary of canonical/desired field values (from docs).

        Returns:
            A :class:`DriftResult` describing any detected drift.
        """
        if not entity_id:
            return DriftResult(
                has_drift=False,
                drift_type="error",
                explanation="Missing entity_id — drift detection skipped.",
                confidence=0.0,
            )

        if observed is None:
            return DriftResult(
                has_drift=False,
                drift_type="error",
                explanation=f"Entity '{entity_id}': observed state is None — cannot compare.",
                confidence=0.0,
            )

        if canonical is None or len(canonical) == 0:
            return DriftResult(
                has_drift=True,
                drift_type="missing_canonical",
                fields_changed=sorted(observed.keys()),
                confidence=0.5,
                explanation=(
                    f"Entity '{entity_id}': no canonical baseline exists. "
                    f"All {len(observed)} observed fields are unvalidated."
                ),
            )

        all_keys = set(observed.keys()) | set(canonical.keys())
        changed: list[str] = []

        for key in sorted(all_keys):
            obs_val = observed.get(key)
            can_val = canonical.get(key)
            if not self._values_equal(obs_val, can_val):
                changed.append(key)

        if not changed:
            return DriftResult(
                has_drift=False,
                drift_type="",
                fields_changed=[],
                confidence=1.0,
                explanation=f"Entity '{entity_id}': no drift detected — "
                            f"observed state matches canonical.",
            )

        drift_type = self._classify_drift(changed)
        confidence = self._compute_confidence(changed, all_keys)
        explanation = self._build_explanation(entity_id, changed, drift_type, observed, canonical)

        return DriftResult(
            has_drift=True,
            drift_type=drift_type,
            fields_changed=changed,
            confidence=confidence,
            explanation=explanation,
        )

    @staticmethod
    def _values_equal(a: Any, b: Any) -> bool:
        """Deep equality check tolerant of type mismatches (str vs int)."""
        if a is None and b is None:
            return True
        if a is None or b is None:
            return False
        if isinstance(a, dict) and isinstance(b, dict):
            return a == b
        if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
            return list(a) == list(b)
        return str(a) == str(b)

    @staticmethod
    def _classify_drift(changed_fields: list[str]) -> str:
        """Classify the overall drift severity based on changed field names.

        Priority: critical > accidental > intentional.
        """
        has_critical = any(f in _CRITICAL_FIELDS for f in changed_fields)
        has_intentional = any(f in _INTENTIONAL_FIELDS for f in changed_fields)

        if has_critical:
            return "critical"

        if has_intentional and all(
            f in _INTENTIONAL_FIELDS for f in changed_fields
        ):
            return "intentional"

        return "accidental"

    @staticmethod
    def _compute_confidence(
        changed: list[str],
        all_keys: set[str],
    ) -> float:
        """Confidence is higher when fewer fields drift and the fields are
        well-known (in the critical or intentional sets)."""
        if not all_keys:
            return 0.5

        known_fields = _CRITICAL_FIELDS | _INTENTIONAL_FIELDS
        known_changed = sum(1 for f in changed if f in known_fields)
        known_ratio = known_changed / len(changed) if changed else 0.0

        base = 0.6
        return round(min(1.0, base + known_ratio * 0.4), 4)

    @staticmethod
    def _build_explanation(
        entity_id: str,
        changed: list[str],
        drift_type: str,
        observed: dict[str, Any],
        canonical: dict[str, Any],
    ) -> str:
        """Build a detailed human-readable drift summary."""
        lines = [
            f"Entity '{entity_id}': {drift_type.upper()} drift detected "
            f"in {len(changed)} field(s).",
        ]
        for f in changed[:10]:
            obs = observed.get(f, "<missing>")
            can = canonical.get(f, "<missing>")
            obs_str = _truncate(str(obs), 80)
            can_str = _truncate(str(can), 80)
            lines.append(f"  {f}: observed={obs_str}  canonical={can_str}")

        if len(changed) > 10:
            lines.append(f"  … and {len(changed) - 10} more field(s).")

        return "\n".join(lines)


def _truncate(s: str, max_len: int) -> str:
    return s if len(s) <= max_len else s[: max_len - 1] + "…"
