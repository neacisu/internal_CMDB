"""Tests for internalcmdb.workers.executor — mocked DB and subprocess."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pytest

from internalcmdb.workers import executor


def test_run_script_unknown_task() -> None:
    with pytest.raises(ValueError, match="Unknown task"):
        executor.run_script(uuid.uuid4(), "nonexistent_task_xyz")


@patch("internalcmdb.workers.executor.subprocess.run")
@patch("internalcmdb.workers.executor._db_session")
def test_run_script_happy_path(mock_db_session: MagicMock, mock_run: MagicMock) -> None:
    job_id = uuid.uuid4()
    mock_job = MagicMock()
    mock_job.status = "queued"
    mock_db = MagicMock()
    mock_db.get.return_value = mock_job
    mock_db_session.return_value = mock_db

    mock_run.return_value = MagicMock(stdout="ok", stderr="", returncode=0)

    executor.run_script(job_id, "ssh_connectivity_check", extra_args=["--dry-run"])

    assert mock_job.status == "completed"
    mock_db.commit.assert_called()
    mock_db.close.assert_called()


@patch("internalcmdb.workers.executor.threading.Thread")
@patch("internalcmdb.workers.executor._db_session")
def test_enqueue_job_creates_thread(mock_db_session: MagicMock, mock_thread: MagicMock) -> None:
    mock_db = MagicMock()
    mock_db_session.return_value = mock_db

    jid = executor.enqueue_job("ssh_connectivity_check", triggered_by="test")

    assert isinstance(jid, uuid.UUID)
    mock_db.add.assert_called_once()
    mock_db.commit.assert_called()
    mock_thread.assert_called_once()
    _args, kwargs = mock_thread.call_args
    assert kwargs.get("daemon") is True
