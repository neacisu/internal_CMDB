"""Worker task executor — runs scripts as subprocesses and persists job history."""

from __future__ import annotations

import json
import subprocess
import sys
import threading
import uuid
from datetime import UTC, datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from internalcmdb.api.config import get_settings

from .models import JobHistory
from .registry import BASE, SCRIPTS


def _db_session() -> Session:
    """Return a throwaway SQLAlchemy session using the same .env as the API."""
    settings = get_settings()
    engine = create_engine(settings.database_url, pool_pre_ping=True)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    return factory()


def run_script(job_id: uuid.UUID, task_name: str, extra_args: list[str] | None = None) -> None:
    """Execute a registered script subprocess and persist stdout/stderr/exit_code."""
    script_def = SCRIPTS.get(task_name)
    if script_def is None:
        raise ValueError(f"Unknown task: {task_name!r}")

    script_abs = BASE / script_def.script_path
    args = [sys.executable, str(script_abs)] + (script_def.default_args or []) + (extra_args or [])

    db = _db_session()
    job: JobHistory | None = None
    try:
        job = db.get(JobHistory, job_id)
        if job is None:
            return

        job.status = "running"
        job.started_at = str(datetime.now(UTC))
        db.commit()

        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            check=False,
            cwd=str(BASE),
        )

        job.stdout = result.stdout[-50_000:] if result.stdout else None  # cap at 50k chars
        job.stderr = result.stderr[-50_000:] if result.stderr else None
        job.exit_code = result.returncode
        job.status = "completed" if result.returncode == 0 else "failed"
        job.finished_at = str(datetime.now(UTC))
        db.commit()
    except Exception as exc:
        if job is not None:
            job.status = "failed"
            job.stderr = str(exc)
            job.finished_at = str(datetime.now(UTC))
            db.commit()
        raise
    finally:
        db.close()


def enqueue_job(
    task_name: str,
    triggered_by: str = "manual",
    extra_args: list[str] | None = None,
    schedule_cron: str | None = None,
) -> uuid.UUID:
    """Create a JobHistory record and dispatch the script in a background thread."""
    job_id = uuid.uuid4()

    db = _db_session()
    try:
        job = JobHistory(
            job_id=job_id,
            task_name=task_name,
            status="queued",
            triggered_by=triggered_by,
            schedule_cron=schedule_cron,
            args_json=json.dumps(extra_args or []),
        )
        db.add(job)
        db.commit()
    finally:
        db.close()

    thread = threading.Thread(
        target=run_script,
        args=(job_id, task_name, extra_args),
        daemon=True,
        name=f"worker-{task_name}-{job_id}",
    )
    thread.start()

    return job_id
