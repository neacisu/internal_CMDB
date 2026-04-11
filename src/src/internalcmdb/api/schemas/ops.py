"""Pydantic v2 schemas for dashboard, workers, and results endpoints."""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel

from .common import DatetimeStr, OptDatetimeStr, OrmBase

# --- Dashboard ---


class EnvironmentCount(BaseModel):
    term_code: str
    display_name: str
    count: int


class DashboardSummary(BaseModel):
    host_count: int
    cluster_count: int
    service_count: int
    gpu_count: int
    docker_host_count: int
    gpu_capable_count: int
    collection_runs_24h: int
    last_run_ts: str | None = None
    total_ram_gb: float
    total_gpu_vram_gb: float
    service_instance_count: int
    hosts_by_environment: list[EnvironmentCount] = []
    hosts_by_lifecycle: list[EnvironmentCount] = []


class GpuSummaryItem(BaseModel):
    host_id: uuid.UUID
    hostname: str
    gpu_index: int
    model_name: str | None = None
    memory_total_mb: int | None = None
    memory_used_mb: int | None = None
    utilization_gpu_pct: float | None = None
    temperature_celsius: float | None = None
    power_draw_watts: float | None = None


class DiskSummaryItem(BaseModel):
    host_id: uuid.UUID
    hostname: str
    device_name: str
    mountpoint_text: str | None = None
    size_bytes: int | None = None
    used_pct: float | None = None


class TrendPoint(BaseModel):
    ts: str
    value: float


class TrendSeries(BaseModel):
    series: str
    points: list[TrendPoint] = []


# --- Workers ---


class ScriptMeta(BaseModel):
    task_name: str
    display_name: str
    description: str
    category: str  # discovery | security | etl | maintenance | governance
    script_path: str
    is_destructive: bool = False


class JobTriggerRequest(BaseModel):
    args: list[str] = []
    kwargs: dict[str, Any] = {}


class JobOut(OrmBase):
    job_id: uuid.UUID
    task_name: str
    status: str
    started_at: OptDatetimeStr = None
    finished_at: OptDatetimeStr = None
    exit_code: int | None = None
    triggered_by: str
    schedule_cron: str | None = None
    created_at: DatetimeStr


class JobDetailOut(JobOut):
    stdout: str | None = None
    stderr: str | None = None
    args_json: str | None = None


class ScheduleCreate(BaseModel):
    task_name: str
    cron_expression: str
    description: str | None = None
    is_active: bool = True


class ScheduleOut(OrmBase):
    schedule_id: uuid.UUID
    task_name: str
    cron_expression: str
    description: str | None = None
    is_active: bool
    next_run_at: OptDatetimeStr = None
    last_run_at: OptDatetimeStr = None
    created_at: DatetimeStr


# --- Results ---


class ResultTypeMeta(BaseModel):
    result_type: str
    display_name: str
    directory: str
    current_file: str | None = None
    last_modified: str | None = None


class ResultHistoryItem(BaseModel):
    filename: str
    modified_at: str
    size_bytes: int
