"""Shared pytest fixtures for internalcmdb tests."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest
from sqlalchemy.orm import Session

from internalcmdb.models.agent_control import (  # pylint: disable=import-error
    ActionRequest,
    AgentRun,
)

# ---------------------------------------------------------------------------
# Session fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_session() -> MagicMock:
    """Return a MagicMock that satisfies the ``Session`` interface."""
    session = MagicMock(spec=Session)
    session.add = MagicMock()
    session.flush = MagicMock()
    return session


# ---------------------------------------------------------------------------
# AgentRun stub factory
# ---------------------------------------------------------------------------


def make_agent_run(
    status: str = "pending",
    run_code: str = "RUN-TEST-001",
    agent_run_id: uuid.UUID | None = None,
) -> MagicMock:
    """Return a lightweight AgentRun mock with the attributes we mutate in tests."""
    run = MagicMock(spec=AgentRun)
    run.agent_run_id = agent_run_id or uuid.uuid4()
    run.run_code = run_code
    run.status_text = status
    run.requested_scope_jsonb = {}
    run.summary_jsonb = {}  # dict[str, Any]; inline annotation unsupported on mock attrs
    return run


# ---------------------------------------------------------------------------
# ActionRequest stub factory
# ---------------------------------------------------------------------------


def make_action_request(
    status: str = "pending",
    action_class: str = "AC-003",
    action_request_id: uuid.UUID | None = None,
    target_entity_ids: list[uuid.UUID] | None = None,
    snapshot_exists: bool = False,
    approval_record_id: uuid.UUID | None = None,
) -> MagicMock:
    """Return a lightweight ActionRequest mock."""
    req = MagicMock(spec=ActionRequest)
    req.action_request_id = action_request_id or uuid.uuid4()
    req.request_code = f"REQ-{action_class}-TEST"
    req.status_text = status
    req.action_class_text = action_class
    entity_ids = target_entity_ids or []
    req.target_scope_jsonb = {
        "entity_ids": [str(e) for e in entity_ids],
        "requested_by": "test-agent",
        "task_type_code": "TT-001",
        "snapshot_exists": snapshot_exists,
    }
    req.requested_change_jsonb = None
    req.approval_record_id = approval_record_id
    req.executed_at = None
    return req
