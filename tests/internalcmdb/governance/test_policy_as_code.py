"""Tests for governance.policy_as_code — hash-chain audit trail."""

from __future__ import annotations

from unittest.mock import MagicMock

from internalcmdb.governance.policy_as_code import PolicyAuditChain, _GENESIS_HASH


def test_compute_hash_deterministic() -> None:
    payload = {"sequence_num": 1, "decision": "allow"}
    h1 = PolicyAuditChain._compute_hash(_GENESIS_HASH, payload)
    h2 = PolicyAuditChain._compute_hash(_GENESIS_HASH, payload)
    assert h1 == h2
    assert len(h1) == 64


def test_record_decision_returns_signed_record() -> None:
    session = MagicMock()
    session.execute.return_value.first.return_value = None
    session.execute.return_value.fetchall.return_value = []

    chain = PolicyAuditChain(session, signing_key="test-key")
    record = chain.record_decision(
        {"type": "deploy", "target": "staging"},
        compliant=True,
        policy_codes=[],
    )

    assert record is not None
    assert record.decision == "allow"
    assert record.sequence_num == 1
    assert record.signature


def test_verify_chain_empty() -> None:
    session = MagicMock()
    session.execute.return_value.fetchall.return_value = []
    result = PolicyAuditChain(session).verify_chain()
    assert result["valid"] is True
    assert result["checked"] == 0
