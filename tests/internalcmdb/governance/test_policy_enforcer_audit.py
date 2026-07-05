"""Tests for PolicyEnforcer audit chain integration."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from internalcmdb.governance.policy_enforcer import PolicyEnforcer


def test_check_records_audit_chain() -> None:
    session = MagicMock()
    session.query.return_value.filter.return_value.all.return_value = []

    with patch("internalcmdb.governance.policy_as_code.PolicyAuditChain") as MockChain:
        mock_chain = MagicMock()
        MockChain.return_value = mock_chain

        result = PolicyEnforcer(session).check({"type": "read", "target": "staging"})

    assert result.compliant is True
    mock_chain.record_decision.assert_called_once()
    call_kwargs = mock_chain.record_decision.call_args.kwargs
    assert call_kwargs["compliant"] is True
