"""Tests for AutonomousLoop escalate/dismiss actions."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from internalcmdb.cognitive.autonomous_loop import AutonomousLoop


@pytest.mark.asyncio
async def test_dismiss_insight_updates_row() -> None:
    loop = AutonomousLoop()

    mock_conn = MagicMock()
    mock_result = MagicMock()
    mock_result.rowcount = 1
    mock_conn.execute.return_value = mock_result
    mock_engine = MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = mock_conn

    with patch("sqlalchemy.create_engine", return_value=mock_engine):
        updated = await loop._dismiss_insight("host-123", "not actionable")

    assert updated is True
    sql = str(mock_conn.execute.call_args[0][0])
    assert "cognitive.insight" in sql
    assert "dismissed" in sql


@pytest.mark.asyncio
async def test_create_escalation_hitl_inserts_item() -> None:
    loop = AutonomousLoop()
    decision = {"confidence": 0.9, "action_type": "escalate"}

    mock_conn = MagicMock()
    mock_engine = MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = mock_conn

    with patch("sqlalchemy.create_engine", return_value=mock_engine):
        item_id = await loop._create_escalation_hitl("host-123", "disk full", decision)

    assert item_id
    sql = str(mock_conn.execute.call_args[0][0])
    assert "governance.hitl_item" in sql
    assert "autonomous_escalation" in sql
