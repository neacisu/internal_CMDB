"""Tests for internalcmdb.control.audit_ledger (pt-018).

Covers:
- open_run: creates an AgentRun with status=pending
- start_run: pending → running transition
- close_run(success=True): running → completed
- close_run(success=False): running → failed with optional failure_reason
- record_denial: pending → failed, stores deny_reasons in scope JSONB
- Terminal guard: any operation on an already-terminal run is rejected
- NOT_FOUND: operations on non-existent run IDs return failure
- record_evidence: creates AgentEvidence row, returns it
- record_event: merges events into scope JSONB
- Confidence score clamping: [0, 1] enforcement
"""

from __future__ import annotations

# pylint: disable=redefined-outer-name
import uuid
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from internalcmdb.control.audit_ledger import (  # pylint: disable=import-error
    AuditLedger,
    EvidenceSpec,
    RunResult,
    RunSpec,
)
from internalcmdb.models.agent_control import (  # pylint: disable=import-error
    AgentEvidence,
    AgentRun,
)

# ---------------------------------------------------------------------------
# Fixtures & helpers
# ---------------------------------------------------------------------------


def _make_run(
    status: str = "pending",
    run_code: str = "RUN-TEST-001",
    run_id: uuid.UUID | None = None,
) -> MagicMock:
    run = MagicMock(spec=AgentRun)
    run.agent_run_id = run_id or uuid.uuid4()
    run.run_code = run_code
    run.status_text = status
    run.requested_scope_jsonb = {}
    run.finished_at = None
    return run


@pytest.fixture
def mock_session() -> MagicMock:
    session = MagicMock()
    session.add = MagicMock()
    session.flush = MagicMock()
    return session


@pytest.fixture
def ledger(mock_session: MagicMock) -> AuditLedger:
    return AuditLedger(mock_session)


def _spec(run_code: str = "RUN-TEST-001", task: str = "TT-001") -> RunSpec:
    return RunSpec(
        run_code=run_code,
        agent_identity="test-agent",
        task_type_code=task,
    )


# ---------------------------------------------------------------------------
# open_run
# ---------------------------------------------------------------------------


class TestOpenRun:
    def test_returns_success_true(self, ledger: AuditLedger, mock_session: MagicMock) -> None:
        # Make session.flush() populate the AgentRun's UUID
        added_runs: list[AgentRun] = []

        def capture_add(obj: object) -> None:
            if isinstance(obj, AgentRun):
                added_runs.append(obj)

        mock_session.add.side_effect = capture_add
        result = ledger.open_run(_spec())
        assert result.success is True
        assert result.new_status == "pending"

    def test_session_add_and_flush_called(
        self, ledger: AuditLedger, mock_session: MagicMock
    ) -> None:
        ledger.open_run(_spec())
        mock_session.add.assert_called_once()
        mock_session.flush.assert_called_once()

    def test_returns_pending_status(self, ledger: AuditLedger) -> None:
        result = ledger.open_run(_spec())
        assert result.new_status == "pending"


# ---------------------------------------------------------------------------
# start_run
# ---------------------------------------------------------------------------


class TestStartRun:
    def test_pending_to_running(self, ledger: AuditLedger, mock_session: MagicMock) -> None:
        run_id = uuid.uuid4()
        mock_run = _make_run(status="pending", run_id=run_id)
        mock_session.get.return_value = mock_run

        result = ledger.start_run(run_id)
        assert result.success is True
        assert result.new_status == "running"
        assert mock_run.status_text == "running"

    def test_not_pending_returns_failure(
        self, ledger: AuditLedger, mock_session: MagicMock
    ) -> None:
        run_id = uuid.uuid4()
        mock_run = _make_run(status="running", run_id=run_id)
        mock_session.get.return_value = mock_run

        result = ledger.start_run(run_id)
        assert result.success is False
        assert any("INVALID_TRANSITION" in e for e in result.errors)

    def test_not_found_returns_failure(self, ledger: AuditLedger, mock_session: MagicMock) -> None:
        mock_session.get.return_value = None
        result = ledger.start_run(uuid.uuid4())
        assert result.success is False
        assert any("NOT_FOUND" in e for e in result.errors)

    def test_terminal_run_rejected(self, ledger: AuditLedger, mock_session: MagicMock) -> None:
        run_id = uuid.uuid4()
        mock_run = _make_run(status="completed", run_id=run_id)
        mock_session.get.return_value = mock_run

        result = ledger.start_run(run_id)
        assert result.success is False
        assert any("TERMINAL_STATUS" in e for e in result.errors)


# ---------------------------------------------------------------------------
# close_run
# ---------------------------------------------------------------------------


class TestCloseRun:
    def test_running_to_completed(self, ledger: AuditLedger, mock_session: MagicMock) -> None:
        run_id = uuid.uuid4()
        mock_run = _make_run(status="running", run_id=run_id)
        mock_session.get.return_value = mock_run

        result = ledger.close_run(run_id, success=True)
        assert result.success is True
        assert result.new_status == "completed"
        assert mock_run.status_text == "completed"
        assert mock_run.finished_at is not None

    def test_running_to_failed(self, ledger: AuditLedger, mock_session: MagicMock) -> None:
        run_id = uuid.uuid4()
        mock_run = _make_run(status="running", run_id=run_id)
        mock_session.get.return_value = mock_run

        result = ledger.close_run(run_id, success=False)
        assert result.success is True
        assert result.new_status == "failed"
        assert mock_run.status_text == "failed"

    def test_failure_reason_stored_in_scope(
        self, ledger: AuditLedger, mock_session: MagicMock
    ) -> None:
        run_id = uuid.uuid4()
        mock_run = _make_run(status="running", run_id=run_id)
        mock_session.get.return_value = mock_run

        ledger.close_run(run_id, success=False, failure_reason="disk full")
        assert mock_run.requested_scope_jsonb.get("failure_reason") == "disk full"

    def test_not_running_returns_invalid_transition(
        self, ledger: AuditLedger, mock_session: MagicMock
    ) -> None:
        run_id = uuid.uuid4()
        mock_run = _make_run(status="pending", run_id=run_id)
        mock_session.get.return_value = mock_run

        result = ledger.close_run(run_id, success=True)
        assert result.success is False
        assert any("INVALID_TRANSITION" in e for e in result.errors)

    def test_terminal_run_rejected(self, ledger: AuditLedger, mock_session: MagicMock) -> None:
        run_id = uuid.uuid4()
        mock_run = _make_run(status="failed", run_id=run_id)
        mock_session.get.return_value = mock_run

        result = ledger.close_run(run_id, success=True)
        assert result.success is False
        assert any("TERMINAL_STATUS" in e for e in result.errors)


# ---------------------------------------------------------------------------
# record_denial
# ---------------------------------------------------------------------------


class TestRecordDenial:
    def test_pending_to_failed_with_deny_reasons(
        self, ledger: AuditLedger, mock_session: MagicMock
    ) -> None:
        run_id = uuid.uuid4()
        mock_run = _make_run(status="pending", run_id=run_id)
        mock_session.get.return_value = mock_run

        result = ledger.record_denial(run_id, deny_reasons=["D-003: no approval", "D-008: quorum"])
        assert result.success is True
        assert result.new_status == "failed"
        assert mock_run.status_text == "failed"

    def test_deny_reasons_stored_in_scope(
        self, ledger: AuditLedger, mock_session: MagicMock
    ) -> None:
        run_id = uuid.uuid4()
        mock_run = _make_run(status="pending", run_id=run_id)
        mock_session.get.return_value = mock_run

        reasons = ["D-003: missing approval record"]
        ledger.record_denial(run_id, deny_reasons=reasons)
        stored = mock_run.requested_scope_jsonb.get("policy_denial_reasons")
        assert stored == reasons

    def test_denied_at_timestamp_stored(self, ledger: AuditLedger, mock_session: MagicMock) -> None:
        run_id = uuid.uuid4()
        mock_run = _make_run(status="pending", run_id=run_id)
        mock_session.get.return_value = mock_run

        ledger.record_denial(run_id, deny_reasons=["D-004: expired"])
        assert "denied_at" in mock_run.requested_scope_jsonb

    def test_terminal_run_rejected(self, ledger: AuditLedger, mock_session: MagicMock) -> None:
        run_id = uuid.uuid4()
        mock_run = _make_run(status="completed", run_id=run_id)
        mock_session.get.return_value = mock_run

        result = ledger.record_denial(run_id, deny_reasons=["too late"])
        assert result.success is False

    def test_not_found_returns_failure(self, ledger: AuditLedger, mock_session: MagicMock) -> None:
        mock_session.get.return_value = None
        result = ledger.record_denial(uuid.uuid4(), deny_reasons=["irrelevant"])
        assert result.success is False
        assert any("NOT_FOUND" in e for e in result.errors)


# ---------------------------------------------------------------------------
# record_evidence
# ---------------------------------------------------------------------------


class TestRecordEvidence:
    def _ev_spec(self, confidence: float | None = 0.9) -> EvidenceSpec:
        return EvidenceSpec(
            entity_kind_term_id=uuid.uuid4(),
            entity_id=uuid.uuid4(),
            evidence_role="MANDATORY_HOST_CONTEXT",
            confidence_score=confidence,
        )

    def test_creates_agent_evidence_row(self, ledger: AuditLedger, mock_session: MagicMock) -> None:
        run_id = uuid.uuid4()
        ledger.record_evidence(run_id, self._ev_spec())
        mock_session.add.assert_called_once()
        mock_session.flush.assert_called_once()

    def test_returns_agent_evidence_instance(self, ledger: AuditLedger) -> None:
        ev = ledger.record_evidence(uuid.uuid4(), self._ev_spec())
        assert isinstance(ev, AgentEvidence)

    def test_confidence_score_clamped_high(self, ledger: AuditLedger) -> None:
        ev = ledger.record_evidence(uuid.uuid4(), self._ev_spec(confidence=1.5))
        assert ev.confidence_score == Decimal("1.0")

    def test_confidence_score_clamped_low(self, ledger: AuditLedger) -> None:
        ev = ledger.record_evidence(uuid.uuid4(), self._ev_spec(confidence=-0.5))
        assert ev.confidence_score == Decimal("0.0")

    def test_none_confidence_remains_none(self, ledger: AuditLedger) -> None:
        ev = ledger.record_evidence(uuid.uuid4(), self._ev_spec(confidence=None))
        assert ev.confidence_score is None


# ---------------------------------------------------------------------------
# record_event
# ---------------------------------------------------------------------------


class TestRecordEvent:
    def test_event_stored_in_scope(self, ledger: AuditLedger, mock_session: MagicMock) -> None:
        run_id = uuid.uuid4()
        mock_run = _make_run(status="running", run_id=run_id)
        mock_session.get.return_value = mock_run

        ledger.record_event(run_id, "policy_warning", {"msg": "evidence missing"})
        events = mock_run.requested_scope_jsonb.get("_audit_events", [])
        assert len(events) == 1
        assert events[0]["event_type"] == "policy_warning"

    def test_multiple_events_accumulate(self, ledger: AuditLedger, mock_session: MagicMock) -> None:
        run_id = uuid.uuid4()
        mock_run = _make_run(status="running", run_id=run_id)
        mock_session.get.return_value = mock_run

        ledger.record_event(run_id, "ev_a", {})
        ledger.record_event(run_id, "ev_b", {})
        events = mock_run.requested_scope_jsonb.get("_audit_events", [])
        assert len(events) == 2

    def test_not_found_run_does_not_raise(
        self, ledger: AuditLedger, mock_session: MagicMock
    ) -> None:
        mock_session.get.return_value = None
        # Should return silently without raising
        ledger.record_event(uuid.uuid4(), "test_event", {})


# ---------------------------------------------------------------------------
# RunResult defaults
# ---------------------------------------------------------------------------


class TestRunResultDefaults:
    def test_errors_default_empty_list(self) -> None:
        r = RunResult(success=True, new_status="pending")
        assert r.errors == []

    def test_agent_run_id_default_none(self) -> None:
        r = RunResult(success=False, new_status="unknown")
        assert r.agent_run_id is None
