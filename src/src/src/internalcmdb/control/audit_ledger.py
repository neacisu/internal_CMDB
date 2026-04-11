"""Agent run audit ledger — persists AgentRun + AgentEvidence for full traceability.

pt-018 [m5-3] — epic-5 sprint-9.
Every material agent execution must leave a reconstructable audit record that links:
  - the prompt template used,
  - the evidence pack assembled,
  - the approval record (if any),
  - per-item evidence roles and confidence scores.

Design decisions:
- AgentRun status follows: pending -> running -> completed | failed.
- AuditLedger.open_run() creates the AgentRun row (status=pending).
- AuditLedger.start_run() transitions to running and records started_at.
- AuditLedger.close_run() transitions to completed/failed and records finished_at.
- AgentEvidence rows are appended via record_evidence(); they may be added at any
  time between open_run() and close_run().
- All mutations call session.flush(); the caller owns the transaction.
- Denied or approved runs must both produce audit records (pt-018 verification).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from internalcmdb.models.agent_control import AgentEvidence, AgentRun

# ---------------------------------------------------------------------------
# Status constants
# ---------------------------------------------------------------------------

_STATUS_PENDING = "pending"
_STATUS_RUNNING = "running"
_STATUS_COMPLETED = "completed"
_STATUS_FAILED = "failed"

_TERMINAL_STATUSES: frozenset[str] = frozenset({_STATUS_COMPLETED, _STATUS_FAILED})

# ---------------------------------------------------------------------------
# Public domain types
# ---------------------------------------------------------------------------


@dataclass
class RunSpec:
    """Input specification for opening a new AgentRun record.

    Attributes:
        run_code: Unique stable run identifier (caller-generated, e.g. "RUN-20240101-abc").
        agent_identity: Identity code of the executing agent or user.
        task_type_code: Task type code for context (TT-001..TT-007).
        prompt_template_registry_id: Optional FK to the template used.
        approval_record_id: Optional FK to the governing approval record.
        evidence_pack_id: Optional FK to the assembled evidence pack.
        requested_scope: Free-form scope descriptor stored as JSONB.
    """

    run_code: str
    agent_identity: str
    task_type_code: str
    prompt_template_registry_id: uuid.UUID | None = None
    approval_record_id: uuid.UUID | None = None
    evidence_pack_id: uuid.UUID | None = None
    requested_scope: dict[str, Any] | None = None


@dataclass
class EvidenceSpec:
    """Input specification for a single AgentEvidence item.

    Attributes:
        entity_kind_term_id: Taxonomy term UUID classifying the entity kind.
        entity_id: UUID of the specific entity (optional if chunk-based).
        document_chunk_id: FK to retrieval.document_chunk (optional).
        evidence_artifact_id: FK to discovery.evidence_artifact (optional).
        evidence_role: Human-readable role string (e.g. "MANDATORY_HOST_CONTEXT").
        confidence_score: Model confidence in [0, 1]; None if not applicable.
    """

    entity_kind_term_id: uuid.UUID
    entity_id: uuid.UUID | None = None
    document_chunk_id: uuid.UUID | None = None
    evidence_artifact_id: uuid.UUID | None = None
    evidence_role: str | None = None
    confidence_score: float | None = None


@dataclass
class RunResult:
    """Result of an AgentRun lifecycle operation.

    Attributes:
        success: Whether the operation was applied.
        agent_run_id: UUID of the affected AgentRun row.
        new_status: Resulting status after the operation.
        errors: Non-empty only on failure.
    """

    success: bool
    agent_run_id: uuid.UUID | None = None
    new_status: str = _STATUS_PENDING
    errors: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Ledger engine
# ---------------------------------------------------------------------------


class AuditLedger:
    """Manages creation and lifecycle progression of AgentRun audit records.

    Usage::

        ledger = AuditLedger(session)
        result = ledger.open_run(spec)           # pending
        result = ledger.start_run(run_id)        # running
        ledger.record_evidence(run_id, ev_spec)  # append evidence items
        result = ledger.close_run(run_id, success=True)  # completed
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    # ------------------------------------------------------------------
    # Run lifecycle
    # ------------------------------------------------------------------

    def open_run(self, spec: RunSpec) -> RunResult:
        """Create an AgentRun row with status=pending.

        Both approved and denied runs should call open_run() so all execution
        attempts leave a reconstructable record, satisfying the pt-018 verification
        requirement that denied runs produce sufficient audit records.
        """
        run = AgentRun(
            run_code=spec.run_code,
            agent_identity=spec.agent_identity,
            task_type_code=spec.task_type_code,
            prompt_template_registry_id=spec.prompt_template_registry_id,
            approval_record_id=spec.approval_record_id,
            evidence_pack_id=spec.evidence_pack_id,
            requested_scope_jsonb=spec.requested_scope,
            status_text=_STATUS_PENDING,
            started_at=datetime.now(tz=UTC).isoformat(),
        )
        self._session.add(run)
        self._session.flush()
        return RunResult(
            success=True,
            agent_run_id=run.agent_run_id,
            new_status=_STATUS_PENDING,
        )

    def start_run(self, agent_run_id: uuid.UUID) -> RunResult:
        """Advance a pending AgentRun to running status."""
        run = self._load(agent_run_id)
        if run is None:
            return _run_not_found(agent_run_id)
        guard = self._guard_terminal(run)
        if guard:
            return guard
        if run.status_text != _STATUS_PENDING:
            return RunResult(
                success=False,
                agent_run_id=run.agent_run_id,
                new_status=run.status_text,
                errors=[f"INVALID_TRANSITION: expected pending, got {run.status_text}"],
            )
        run.status_text = _STATUS_RUNNING
        self._session.flush()
        return RunResult(
            success=True,
            agent_run_id=run.agent_run_id,
            new_status=_STATUS_RUNNING,
        )

    def close_run(
        self,
        agent_run_id: uuid.UUID,
        *,
        success: bool,
        failure_reason: str | None = None,
    ) -> RunResult:
        """Close a running AgentRun as completed or failed.

        A failed run with a *failure_reason* stores the reason in
        requested_scope_jsonb so investigators can reconstruct why the run ended.
        """
        run = self._load(agent_run_id)
        if run is None:
            return _run_not_found(agent_run_id)
        guard = self._guard_terminal(run)
        if guard:
            return guard
        if run.status_text != _STATUS_RUNNING:
            return RunResult(
                success=False,
                agent_run_id=run.agent_run_id,
                new_status=run.status_text,
                errors=[f"INVALID_TRANSITION: expected running, got {run.status_text}"],
            )
        now = datetime.now(tz=UTC).isoformat()
        run.finished_at = now
        if success:
            run.status_text = _STATUS_COMPLETED
        else:
            run.status_text = _STATUS_FAILED
            if failure_reason:
                existing = dict(run.requested_scope_jsonb or {})
                existing["failure_reason"] = failure_reason
                run.requested_scope_jsonb = existing
        self._session.flush()
        return RunResult(
            success=True,
            agent_run_id=run.agent_run_id,
            new_status=run.status_text,
        )

    def record_denial(
        self,
        agent_run_id: uuid.UUID,
        deny_reasons: list[str],
    ) -> RunResult:
        """Record a policy denial for an open (pending) run without transitioning to running.

        This allows calling code to open a run, immediately discover it is denied, and
        persist the denial reasons before closing as failed — ensuring that denied runs
        leave sufficient audit records (pt-018 verification).
        """
        run = self._load(agent_run_id)
        if run is None:
            return _run_not_found(agent_run_id)
        guard = self._guard_terminal(run)
        if guard:
            return guard
        existing = dict(run.requested_scope_jsonb or {})
        existing["policy_denial_reasons"] = deny_reasons
        existing["denied_at"] = datetime.now(tz=UTC).isoformat()
        run.requested_scope_jsonb = existing
        run.status_text = _STATUS_FAILED
        run.finished_at = datetime.now(tz=UTC).isoformat()
        self._session.flush()
        return RunResult(
            success=True,
            agent_run_id=run.agent_run_id,
            new_status=_STATUS_FAILED,
        )

    # ------------------------------------------------------------------
    # Evidence accumulation
    # ------------------------------------------------------------------

    def record_evidence(self, agent_run_id: uuid.UUID, spec: EvidenceSpec) -> AgentEvidence:
        """Append an AgentEvidence row to the specified run.

        Confidence scores are clamped to [0.0, 1.0] to prevent DB constraint errors.
        """
        clamped_score: Decimal | None = None
        if spec.confidence_score is not None:
            clamped_score = Decimal(str(max(0.0, min(1.0, spec.confidence_score))))
        ev = AgentEvidence(
            agent_run_id=agent_run_id,
            entity_kind_term_id=spec.entity_kind_term_id,
            entity_id=spec.entity_id,
            document_chunk_id=spec.document_chunk_id,
            evidence_artifact_id=spec.evidence_artifact_id,
            evidence_role_text=spec.evidence_role,
            confidence_score=clamped_score,
        )
        self._session.add(ev)
        self._session.flush()
        return ev

    def record_event(
        self,
        agent_run_id: uuid.UUID,
        event_type: str,
        payload: dict[str, Any],
    ) -> None:
        """Merge an audit event into the AgentRun's requested_scope_jsonb.

        Used by callers to attach structured events (e.g. denial reasons,
        policy warnings) without creating separate rows.
        """
        run = self._load(agent_run_id)
        if run is None:
            return
        existing = dict(run.requested_scope_jsonb or {})
        events: list[dict[str, Any]] = existing.get("_audit_events", [])
        events.append(
            {
                "event_type": event_type,
                "recorded_at": datetime.now(tz=UTC).isoformat(),
                "payload": payload,
            }
        )
        existing["_audit_events"] = events
        run.requested_scope_jsonb = existing
        self._session.flush()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _load(self, agent_run_id: uuid.UUID) -> AgentRun | None:
        result = self._session.get(AgentRun, agent_run_id)
        return result if isinstance(result, AgentRun) else None

    def _guard_terminal(self, run: AgentRun) -> RunResult | None:
        if run.status_text in _TERMINAL_STATUSES:
            return RunResult(
                success=False,
                agent_run_id=run.agent_run_id,
                new_status=run.status_text,
                errors=[f"TERMINAL_STATUS: run {run.run_code} is already {run.status_text}"],
            )
        return None


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def make_run_code(agent_identity: str, task_type_code: str) -> str:
    """Generate a unique, human-readable run code."""
    ts = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%S")
    suffix = uuid.uuid4().hex[:6].upper()
    safe_identity = agent_identity[:8].replace(" ", "_")
    return f"RUN-{safe_identity}-{task_type_code}-{ts}-{suffix}"


def _run_not_found(agent_run_id: uuid.UUID) -> RunResult:
    return RunResult(
        success=False,
        new_status="unknown",
        errors=[f"NOT_FOUND: AgentRun {agent_run_id} does not exist"],
    )
