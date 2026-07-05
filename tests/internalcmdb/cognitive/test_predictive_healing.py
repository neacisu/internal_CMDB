"""Tests for cognitive.predictive_healing — anomaly detection."""

from __future__ import annotations

from unittest.mock import MagicMock

from internalcmdb.cognitive.predictive_healing import PredictiveHealingEngine


def test_detect_anomalies_absolute_threshold() -> None:
    engine = PredictiveHealingEngine(MagicMock())
    vitals = [
        {"agent_id": "a1", "host_code": "hz-223", "cpu_pct": 50.0, "memory_pct": 40.0},
        {"agent_id": "a2", "host_code": "hz-224", "cpu_pct": 95.0, "memory_pct": 40.0},
    ]
    anomalies = engine.detect_anomalies(vitals)
    cpu_anomalies = [a for a in anomalies if a.metric == "cpu_pct"]
    assert len(cpu_anomalies) == 1
    assert cpu_anomalies[0].host_code == "hz-224"
    assert cpu_anomalies[0].severity in ("warning", "critical")


def test_propose_remediation_policy_gate() -> None:
    session = MagicMock()
    session.query.return_value.filter.return_value.all.return_value = []

    engine = PredictiveHealingEngine(session)
    from internalcmdb.cognitive.predictive_healing import VitalsAnomaly

    anomaly = VitalsAnomaly(
        agent_id="a1",
        host_code="hz-223",
        metric="cpu_pct",
        value=95.0,
        threshold=90.0,
        severity="critical",
        reason="absolute",
    )
    proposal = engine.propose_remediation(anomaly)
    assert proposal.policy_compliant is True
    assert proposal.action["target"] == "hz-223"
    assert proposal.hitl_required is True
