"""Router: workers — script management, job history, scheduling."""

from __future__ import annotations

import json
import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from internalcmdb.workers.executor import enqueue_job
from internalcmdb.workers.models import JobHistory, WorkerSchedule
from internalcmdb.workers.registry import SCRIPTS

from ..deps import get_db
from ..schemas.common import Page, PageMeta, paginate
from ..schemas.ops import (
    JobDetailOut,
    JobOut,
    JobTriggerRequest,
    ScheduleCreate,
    ScheduleOut,
    ScriptMeta,
)

router = APIRouter(prefix="/workers", tags=["workers"])


@router.get("/scripts", response_model=list[ScriptMeta])
def list_scripts() -> list[ScriptMeta]:
    """Return the static registry of all available worker scripts."""
    return [
        ScriptMeta(
            task_name=s.task_name,
            display_name=s.display_name,
            description=s.description,
            category=s.category,
            script_path=s.script_path,
            is_destructive=s.is_destructive,
        )
        for s in SCRIPTS.values()
    ]


@router.post("/run/{task_name}", response_model=dict)
def run_task(
    task_name: str,
    body: JobTriggerRequest,
) -> dict:  # type: ignore[type-arg]
    if task_name not in SCRIPTS:
        raise HTTPException(status_code=404, detail=f"Unknown task: {task_name!r}")
    job_id = enqueue_job(
        task_name=task_name,
        triggered_by="ui",
        extra_args=body.args or None,
    )
    return {"job_id": str(job_id), "status": "queued"}


@router.get("/jobs", response_model=Page[JobOut])
def list_jobs(
    db: Annotated[Session, Depends(get_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    task_name: str | None = None,
    status: str | None = None,
) -> Page[JobOut]:
    q = db.query(JobHistory)
    if task_name is not None:
        q = q.filter(JobHistory.task_name == task_name)
    if status is not None:
        q = q.filter(JobHistory.status == status)
    q = q.order_by(JobHistory.created_at.desc())
    items, total = paginate(q, page, page_size)
    return Page(items=items, meta=PageMeta(page=page, page_size=page_size, total=total))


@router.get("/jobs/{job_id}", response_model=JobDetailOut)
def get_job(job_id: uuid.UUID, db: Annotated[Session, Depends(get_db)]) -> JobHistory:
    job = db.get(JobHistory, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.post("/jobs/{job_id}/retry", response_model=dict)
def retry_job(
    job_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    job = db.get(JobHistory, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status not in ("failed", "cancelled"):
        raise HTTPException(
            status_code=400,
            detail="Only failed or cancelled jobs can be retried",
        )

    extra_args = json.loads(job.args_json) if job.args_json else None
    new_id = enqueue_job(
        task_name=job.task_name,
        triggered_by="retry",
        extra_args=extra_args,
    )
    return {"job_id": str(new_id), "status": "queued"}


@router.delete("/jobs/{job_id}", status_code=204)
def cancel_job(job_id: uuid.UUID, db: Annotated[Session, Depends(get_db)]) -> None:
    job = db.get(JobHistory, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status not in ("queued",):
        raise HTTPException(status_code=400, detail="Only queued jobs can be cancelled")
    job.status = "cancelled"
    db.commit()


# --- Schedules ---


@router.get("/schedules", response_model=list[ScheduleOut])
def list_schedules(db: Annotated[Session, Depends(get_db)]) -> list[WorkerSchedule]:
    return db.scalars(  # type: ignore[return-value]
        select(WorkerSchedule).order_by(WorkerSchedule.task_name)
    ).all()


@router.post("/schedules", response_model=ScheduleOut, status_code=201)
def create_schedule(
    body: ScheduleCreate,
    db: Annotated[Session, Depends(get_db)],
) -> WorkerSchedule:
    if body.task_name not in SCRIPTS:
        raise HTTPException(status_code=404, detail=f"Unknown task: {body.task_name!r}")
    schedule = WorkerSchedule(
        task_name=body.task_name,
        cron_expression=body.cron_expression,
        description=body.description,
        is_active=body.is_active,
    )
    db.add(schedule)
    db.commit()
    db.refresh(schedule)
    return schedule


@router.put("/schedules/{schedule_id}", response_model=ScheduleOut)
def update_schedule(
    schedule_id: uuid.UUID,
    body: ScheduleCreate,
    db: Annotated[Session, Depends(get_db)],
) -> WorkerSchedule:
    schedule = db.get(WorkerSchedule, schedule_id)
    if schedule is None:
        raise HTTPException(status_code=404, detail="Schedule not found")
    schedule.cron_expression = body.cron_expression
    schedule.description = body.description
    schedule.is_active = body.is_active
    db.commit()
    db.refresh(schedule)
    return schedule


@router.delete("/schedules/{schedule_id}", status_code=204)
def delete_schedule(schedule_id: uuid.UUID, db: Annotated[Session, Depends(get_db)]) -> None:
    schedule = db.get(WorkerSchedule, schedule_id)
    if schedule is None:
        raise HTTPException(status_code=404, detail="Schedule not found")
    db.delete(schedule)
    db.commit()
