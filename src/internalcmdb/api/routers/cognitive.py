"""Router: cognitive — NL queries, insights, health scores, drift, reports, self-heal."""

from __future__ import annotations

import logging
import os
import uuid
from collections.abc import Awaitable
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Annotated, Any, cast

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import Row, text
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from ..deps import get_async_session
from ..middleware.rate_limit import rate_limit
from ..middleware.rbac import require_role

if TYPE_CHECKING:
    from redis.asyncio import Redis as _AioRedis
    from redis.asyncio.client import PubSub as _AioPubSub

    from internalcmdb.cognitive.analyzer import AnalysisResult

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cognitive", tags=["cognitive"])


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------


class NLQueryRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    top_k: int = Field(default=8, ge=1, le=30)


class SourceChunk(BaseModel):
    chunk_id: str
    content: str
    section: str | None = None
    distance: float | None = None


class NLQueryResponse(BaseModel):
    answer: str
    sources: list[SourceChunk] = []
    confidence: float = 0.0
    tokens_used: int = 0


def _label_insight(meta: dict[str, Any]) -> str:
    """Return a display label for a ``cognitive_insight`` source chunk."""
    cat: str = str(meta.get("category") or "insight")
    sev: str = str(meta.get("severity") or "")
    return f"{cat}/{sev}" if sev else cat


def _label_file_source(meta: dict[str, Any], src: str) -> str:
    """Return a display label for a ``docs`` or ``subprojects`` source chunk."""
    file_path: str = str(meta.get("file") or "")
    if file_path:
        return os.path.splitext(os.path.basename(file_path))[0]
    return src


def _source_label(s: dict[str, Any]) -> str:
    """Build a human-readable label for a source chunk from its metadata."""
    meta: dict[str, Any] = cast(dict[str, Any], s.get("metadata") or {})
    src: str = str(meta.get("source") or "")
    if src == "cmdb_host":
        return str(meta.get("host_code") or "host")
    if src == "cmdb_service":
        return str(meta.get("service_code") or "service")
    if src == "cognitive_insight":
        return _label_insight(meta)
    if src in ("docs", "subprojects"):
        return _label_file_source(meta, src)
    # Fallback: use section_path_text if populated, else source tag
    return str(s.get("section") or src or "source")


class AnalyzeRequest(BaseModel):
    include_facts: bool = True
    include_services: bool = True


class AnalysisOut(BaseModel):
    entity_id: str
    entity_type: str
    is_anomaly: bool = False
    severity: str = "info"
    category: str = "reliability"
    confidence: float = 0.0
    explanation: str = ""
    facts_analyzed: int = 0
    timestamp: str | None = None


class InsightOut(BaseModel):
    insight_id: str
    entity_id: str | None = None
    entity_type: str | None = None
    severity: str = "info"
    category: str | None = None
    title: str = ""
    description: str = ""
    remediation: str | None = None
    status: str = "active"
    confidence: float = 0.0
    evidence: list[dict[str, Any]] = []  # Pydantic v2 copies mutable defaults safely
    created_at: str | None = None
    acknowledged_by: str | None = None
    dismissed_reason: str | None = None


class AckBody(BaseModel):
    acknowledged_by: str


class DismissBody(BaseModel):
    dismissed_by: str
    reason: str


class HealthScoreOut(BaseModel):
    entity_id: str
    entity_type: str
    score: int
    breakdown: dict[str, Any] = Field(default_factory=dict)
    status: str = "unknown"
    timestamp: str | None = None


class ReportOut(BaseModel):
    report_id: str
    report_kind: str
    title: str = ""
    content: str = ""
    generated_at: str | None = None
    generated_by: str = "system"


class ReportGenerateRequest(BaseModel):
    report_kind: str = Field(
        pattern=r"^(fleet|security|capacity)$",
        description="One of: fleet, security, capacity",
    )
    scope: dict[str, Any] = Field(default_factory=dict)


class DriftCheckRequest(BaseModel):
    entity_type: str | None = None
    entity_id: str | None = None


class DriftResultOut(BaseModel):
    drift_id: str
    entity_id: str
    entity_type: str = "host"
    has_drift: bool = False
    drift_type: str = ""
    fields_changed: list[str] = Field(default_factory=list)
    confidence: float = 1.0
    explanation: str = ""
    detected_at: str | None = None


class SelfHealActionOut(BaseModel):
    action_id: str
    playbook_name: str
    entity_id: str | None = None
    status: str = "completed"
    result_summary: str = ""
    executed_at: str | None = None
    executed_by: str = "system"


class PlaybookOut(BaseModel):
    playbook_id: str
    name: str
    description: str = ""
    trigger_conditions: list[str] = Field(default_factory=list)
    risk_level: str = "low"
    is_active: bool = True


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _row_to_dict(row: Any) -> dict[str, Any]:
    mapping = row._mapping
    result: dict[str, Any] = {}
    for k, v in mapping.items():
        if hasattr(v, "isoformat"):
            result[k] = v.isoformat()
        elif isinstance(v, uuid.UUID):
            result[k] = str(v)
        else:
            result[k] = v
    return result


def _now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


# ---------------------------------------------------------------------------
# NL Query (RAG)
# ---------------------------------------------------------------------------


@router.post(
    "/query",
    response_model=NLQueryResponse,
    dependencies=[Depends(require_role("operator", "platform_admin", "viewer"))],
)
@rate_limit("10/minute")
async def cognitive_query(
    request: Request,
    body: NLQueryRequest,
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> NLQueryResponse:
    """Natural language query with RAG over the InternalCMDB knowledge base."""
    try:
        from internalcmdb.cognitive.query_engine import QueryEngine  # noqa: PLC0415
        from internalcmdb.llm.client import LLMClient  # noqa: PLC0415

        llm = LLMClient()
        engine = QueryEngine(llm, session, top_k=body.top_k)
        result = await engine.query(body.question)

        return NLQueryResponse(
            answer=result.answer,
            sources=[
                SourceChunk(
                    chunk_id=s.get("chunk_id", ""),
                    content=s.get("content", ""),
                    section=_source_label(s),
                    distance=s.get("distance"),
                )
                for s in result.sources
            ],
            confidence=result.confidence,
            tokens_used=result.tokens_used,
        )
    except Exception as exc:
        return NLQueryResponse(
            answer=f"Query engine unavailable: {exc}",
            confidence=0.0,
        )


# ---------------------------------------------------------------------------
# Analyze host / service
# ---------------------------------------------------------------------------


@router.post(
    "/analyze/host/{host_id}",
    response_model=AnalysisOut,
    dependencies=[Depends(require_role("operator", "platform_admin"))],
)
async def analyze_host(
    host_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> AnalysisOut:
    """Cognitive analysis of a specific host — anomaly detection on recent facts."""
    result = await session.execute(
        text("""
            SELECT fact_namespace, fact_key, fact_value_jsonb, entity_id
            FROM discovery.observed_fact
            WHERE entity_id = :eid
            ORDER BY observed_at DESC
            LIMIT 50
        """),
        {"eid": str(host_id)},
    )
    facts = result.fetchall()

    try:
        from internalcmdb.cognitive.analyzer import FactAnalyzer  # noqa: PLC0415

        analyzer = FactAnalyzer(session)
        anomalies: list[AnalysisResult] = []
        for f in facts:
            m = f._mapping
            ar = await analyzer.analyze_fact(
                {
                    "entity_id": str(m["entity_id"]),
                    "fact_namespace": m["fact_namespace"],
                    "fact_key": m["fact_key"],
                    "fact_value_jsonb": m["fact_value_jsonb"],
                }
            )
            if ar.is_anomaly:
                anomalies.append(ar)

        worst: AnalysisResult | None = (
            max(anomalies, key=lambda a: a.confidence) if anomalies else None
        )

        return AnalysisOut(
            entity_id=str(host_id),
            entity_type="host",
            is_anomaly=bool(anomalies),
            severity=worst.severity if worst else "info",
            category=worst.category if worst else "reliability",
            confidence=worst.confidence if worst else 0.5,
            explanation=worst.explanation if worst else "No anomalies detected.",
            facts_analyzed=len(facts),
            timestamp=_now_iso(),
        )
    except Exception as exc:
        return AnalysisOut(
            entity_id=str(host_id),
            entity_type="host",
            explanation=f"Analysis unavailable: {exc}",
            facts_analyzed=len(facts),
            timestamp=_now_iso(),
        )


@router.post(
    "/analyze/service/{service_id}",
    response_model=AnalysisOut,
    dependencies=[Depends(require_role("operator", "platform_admin"))],
)
async def analyze_service(
    service_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> AnalysisOut:
    """Cognitive analysis of a specific service — checks service instances and related facts."""
    result = await session.execute(
        text("""
            SELECT si.host_id, si.status_text, si.observed_at
            FROM registry.service_instance si
            WHERE si.shared_service_id = :sid
            ORDER BY si.observed_at DESC NULLS LAST
        """),
        {"sid": str(service_id)},
    )
    instances = result.fetchall()

    unhealthy = [
        r for r in instances if r._mapping.get("status_text") not in ("running", "active", None)
    ]
    n_inst = len(instances)
    n_unhealthy = len(unhealthy)
    if n_unhealthy > n_inst / 2:
        severity = "critical"
    elif n_unhealthy > 0:
        severity = "warning"
    else:
        severity = "info"

    return AnalysisOut(
        entity_id=str(service_id),
        entity_type="service",
        is_anomaly=bool(unhealthy),
        severity=severity,
        category="reliability",
        confidence=0.8 if instances else 0.3,
        explanation=(
            f"{len(unhealthy)} / {len(instances)} instances unhealthy."
            if unhealthy
            else f"All {len(instances)} instances healthy."
        ),
        facts_analyzed=len(instances),
        timestamp=_now_iso(),
    )


# ---------------------------------------------------------------------------
# Insights
# ---------------------------------------------------------------------------


_VALID_INSIGHT_STATUSES = {"active", "acknowledged", "dismissed"}


@router.get(
    "/insights",
    response_model=list[InsightOut],
    dependencies=[Depends(require_role("operator", "platform_admin", "viewer"))],
)
async def list_insights(
    session: Annotated[AsyncSession, Depends(get_async_session)],
    status: str = Query("active", description="Filter: active, acknowledged, dismissed"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> list[dict[str, Any]]:
    """List active cognitive insights (paginated)."""
    if status not in _VALID_INSIGHT_STATUSES:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid status '{status}'. Must be one of: {sorted(_VALID_INSIGHT_STATUSES)}",
        )
    offset = (page - 1) * page_size
    try:
        result = await session.execute(
            text("""
                SELECT insight_id, entity_id, entity_type, severity, category,
                       title, explanation AS description, status, confidence,
                       created_at, acknowledged_by, dismissed_reason
                FROM cognitive.insight
                WHERE status = :status
                ORDER BY
                    CASE severity
                        WHEN 'critical' THEN 1
                        WHEN 'warning'  THEN 2
                        WHEN 'info'     THEN 3
                        ELSE 4
                    END,
                    created_at DESC
                LIMIT :limit OFFSET :offset
            """),
            {"status": status, "limit": page_size, "offset": offset},
        )
        return [_row_to_dict(r) for r in result.fetchall()]
    except Exception:
        return []


@router.get(
    "/insights/{insight_id}",
    response_model=InsightOut,
    dependencies=[Depends(require_role("operator", "platform_admin", "viewer"))],
)
async def get_insight(
    insight_id: str,
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> dict[str, Any]:
    """Get insight details with evidence."""
    try:
        result = await session.execute(
            text("""
                SELECT insight_id, entity_id, entity_type, severity, category,
                       title, explanation AS description, status, confidence,
                       created_at, acknowledged_by, dismissed_reason
                FROM cognitive.insight WHERE insight_id = :iid
            """),
            {"iid": insight_id},
        )
        row = result.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Insight not found")
        return _row_to_dict(row)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=404, detail="Insight not found") from exc


class InsightActionResponse(BaseModel):
    insight_id: str
    status: str


@router.post(
    "/insights/{insight_id}/ack",
    response_model=InsightActionResponse,
    dependencies=[Depends(require_role("operator", "platform_admin"))],
)
async def acknowledge_insight(
    insight_id: str,
    body: AckBody,
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> InsightActionResponse:
    """Acknowledge an active insight."""
    result = cast(
        CursorResult[Any],
        await session.execute(
            text("""
                UPDATE cognitive.insight
                SET status = 'acknowledged', acknowledged_by = :by, updated_at = NOW()
                WHERE insight_id = :iid AND status = 'active'
            """),
            {"iid": insight_id, "by": body.acknowledged_by},
        ),
    )
    await session.commit()
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Insight not found or not in 'active' status")
    return InsightActionResponse(insight_id=insight_id, status="acknowledged")


@router.post(
    "/insights/{insight_id}/dismiss",
    response_model=InsightActionResponse,
    dependencies=[Depends(require_role("operator", "platform_admin"))],
)
async def dismiss_insight(
    insight_id: str,
    body: DismissBody,
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> InsightActionResponse:
    """Dismiss an insight with a reason."""
    result = cast(
        CursorResult[Any],
        await session.execute(
            text("""
                UPDATE cognitive.insight
                SET status = 'dismissed', dismissed_reason = :reason, updated_at = NOW()
                WHERE insight_id = :iid AND status IN ('active', 'acknowledged')
            """),
            {"iid": insight_id, "reason": body.reason},
        ),
    )
    await session.commit()
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Insight not found or already dismissed")
    return InsightActionResponse(insight_id=insight_id, status="dismissed")


# ---------------------------------------------------------------------------
# Health Scores
# ---------------------------------------------------------------------------


async def _fetch_host_snapshot_rows(
    session: AsyncSession,
    limit: int,
    offset: int,
) -> list[Row[Any]]:
    result = await session.execute(
        text("""
            SELECT h.host_id, h.host_code,
                   vitals.payload_jsonb AS vitals_payload,
                   disk.payload_jsonb AS disk_payload,
                   docker.payload_jsonb AS docker_payload
            FROM registry.host h
            LEFT JOIN LATERAL (
                SELECT cs.payload_jsonb
                FROM discovery.collector_snapshot cs
                JOIN discovery.collector_agent ca ON ca.agent_id = cs.agent_id
                WHERE ca.host_id = h.host_id AND cs.snapshot_kind = 'system_vitals'
                ORDER BY cs.collected_at DESC LIMIT 1
            ) vitals ON true
            LEFT JOIN LATERAL (
                SELECT cs.payload_jsonb
                FROM discovery.collector_snapshot cs
                JOIN discovery.collector_agent ca ON ca.agent_id = cs.agent_id
                WHERE ca.host_id = h.host_id AND cs.snapshot_kind = 'disk_state'
                ORDER BY cs.collected_at DESC LIMIT 1
            ) disk ON true
            LEFT JOIN LATERAL (
                SELECT cs.payload_jsonb
                FROM discovery.collector_snapshot cs
                JOIN discovery.collector_agent ca ON ca.agent_id = cs.agent_id
                WHERE ca.host_id = h.host_id AND cs.snapshot_kind = 'docker_state'
                ORDER BY cs.collected_at DESC LIMIT 1
            ) docker ON true
            ORDER BY h.host_code
            LIMIT :limit OFFSET :offset
        """),
        {"limit": limit, "offset": offset},
    )
    return list(result.fetchall())


def _parse_mem_pct(vitals_payload: dict[str, Any]) -> float:
    mem_kb: dict[str, Any] = cast(dict[str, Any], vitals_payload.get("memory_kb") or {})
    mem_total = float(mem_kb.get("MemTotal") or 0)
    mem_avail = float(mem_kb.get("MemAvailable") or mem_kb.get("MemFree") or 0)
    return ((mem_total - mem_avail) / mem_total * 100) if mem_total > 0 else 0.0


def _parse_cpu_pct(vitals_payload: dict[str, Any]) -> float:
    cpu_times: dict[str, Any] = cast(dict[str, Any], vitals_payload.get("cpu_times") or {})
    cpu_idle = float(cpu_times.get("idle") or 0)
    cpu_total = sum(float(v) for v in cpu_times.values()) if cpu_times else 0
    if cpu_total <= 0:
        return 0.0
    return max(0.0, min((cpu_total - cpu_idle) / cpu_total * 100, 100.0))


def _parse_root_disk_pct(disk_payload: dict[str, Any]) -> float:
    for d in cast(list[dict[str, Any]], disk_payload.get("disks") or []):
        if d.get("mountpoint", "") == "/":
            raw = str(d.get("used_pct", "0")).replace("%", "")
            try:
                return float(raw)
            except ValueError:
                return 0.0
    return 0.0


def _parse_container_counts(docker_payload: dict[str, Any]) -> tuple[int, int]:
    containers: list[Any] = cast(list[Any], docker_payload.get("containers") or [])
    running = sum(
        1
        for c in containers
        if isinstance(c, dict) and "Up" in str(cast(dict[str, Any], c).get("status", ""))
    )
    return len(containers), running


def _score_single_host(m: Any, scorer: Any) -> HealthScoreOut:
    vp = cast(dict[str, Any], m.get("vitals_payload") or {})
    dp = cast(dict[str, Any], m.get("disk_payload") or {})
    docker_p = cast(dict[str, Any], m.get("docker_payload") or {})

    cpu_pct = _parse_cpu_pct(vp)
    mem_pct = _parse_mem_pct(vp)
    disk_pct = _parse_root_disk_pct(dp)
    total_containers, running = _parse_container_counts(docker_p)

    host_data = {
        "host_id": str(m["host_id"]),
        "cpu_usage_pct": cpu_pct,
        "memory_usage_pct": mem_pct,
        "disk_usage_pct": disk_pct,
        "services_total": max(total_containers, 1),
        "services_healthy": max(running, 1) if total_containers > 0 else 1,
    }
    hs = scorer.score_host(host_data)
    return HealthScoreOut(
        entity_id=hs.entity_id,
        entity_type=hs.entity_type,
        score=hs.score,
        breakdown={
            **hs.breakdown,
            "host_code": str(m.get("host_code", "")),
            "cpu_pct": round(cpu_pct, 1),
            "mem_pct": round(mem_pct, 1),
            "disk_pct": round(disk_pct, 1),
        },
        status=hs.breakdown.get("status", "unknown"),
        timestamp=hs.timestamp,
    )


@router.get(
    "/health-scores",
    response_model=list[HealthScoreOut],
    dependencies=[Depends(require_role("operator", "platform_admin", "viewer"))],
)
async def list_health_scores(
    session: Annotated[AsyncSession, Depends(get_async_session)],
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> list[HealthScoreOut]:
    """Live health scores for all hosts using real system_vitals + disk_state snapshots."""
    offset = (page - 1) * page_size
    try:
        from internalcmdb.cognitive.health_scorer import HealthScorer  # noqa: PLC0415

        scorer = HealthScorer()
        rows = await _fetch_host_snapshot_rows(session, page_size, offset)
        return [_score_single_host(r._mapping, scorer) for r in rows]
    except Exception as exc:
        logger.warning("Health scores failed: %s", exc, exc_info=True)
        return []


_VALID_ENTITY_TYPES = {"host", "service", "cluster"}


@router.get(
    "/health-scores/{entity_type}/{entity_id}",
    response_model=HealthScoreOut,
    dependencies=[Depends(require_role("operator", "platform_admin", "viewer"))],
)
async def get_health_score(
    entity_type: str,
    entity_id: uuid.UUID,
    _session: Annotated[AsyncSession, Depends(get_async_session)],
) -> HealthScoreOut:
    """Detailed health score for a specific entity."""
    if entity_type not in _VALID_ENTITY_TYPES:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Invalid entity_type '{entity_type}'. Must be one of: "
                f"{sorted(_VALID_ENTITY_TYPES)}"
            ),
        )
    try:
        from internalcmdb.cognitive.health_scorer import HealthScorer  # noqa: PLC0415

        scorer = HealthScorer()
        host_data = {
            "host_id": str(entity_id),
            "cpu_usage_pct": 0.0,
            "memory_usage_pct": 0.0,
            "disk_usage_pct": 0.0,
            "services_total": 0,
            "services_healthy": 0,
        }
        hs = scorer.score_host(host_data)
        return HealthScoreOut(
            entity_id=hs.entity_id,
            entity_type=entity_type,
            score=hs.score,
            breakdown=hs.breakdown,
            status=hs.breakdown.get("status", "unknown"),
            timestamp=hs.timestamp,
        )
    except Exception as exc:
        logger.exception("Health score computation failed for entity %s", entity_id)
        raise HTTPException(status_code=500, detail="Health score computation failed") from exc


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------


@router.get(
    "/reports",
    response_model=list[ReportOut],
    dependencies=[Depends(require_role("operator", "platform_admin", "viewer"))],
)
async def list_reports(
    session: Annotated[AsyncSession, Depends(get_async_session)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> list[dict[str, Any]]:
    """List generated cognitive reports (paginated)."""
    offset = (page - 1) * page_size
    try:
        result = await session.execute(
            text("""
                SELECT report_id, report_type AS report_kind, title,
                       content_markdown AS content,
                       created_at AS generated_at, generated_by
                FROM cognitive.report
                ORDER BY created_at DESC
                LIMIT :limit OFFSET :offset
            """),
            {"limit": page_size, "offset": offset},
        )
        return [_row_to_dict(r) for r in result.fetchall()]
    except Exception:
        return []


@router.get(
    "/reports/{report_id}",
    response_model=ReportOut,
    dependencies=[Depends(require_role("operator", "platform_admin", "viewer"))],
)
async def get_report(
    report_id: str,
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> dict[str, Any]:
    """Get full report content."""
    try:
        result = await session.execute(
            text("SELECT * FROM cognitive.report WHERE report_id = :rid"),
            {"rid": report_id},
        )
        row = result.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Report not found")
        return _row_to_dict(row)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=404, detail="Report not found") from exc


@router.post(
    "/reports/generate",
    response_model=ReportOut,
    status_code=201,
    dependencies=[Depends(require_role("operator", "platform_admin"))],
)
async def generate_report(
    body: ReportGenerateRequest,
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> ReportOut:
    """Trigger manual LLM-powered report generation."""
    report_id = str(uuid.uuid4())
    now = _now_iso()

    try:
        from internalcmdb.cognitive.report_generator import ReportGenerator  # noqa: PLC0415
        from internalcmdb.llm.client import LLMClient  # noqa: PLC0415

        llm = LLMClient()
        gen = ReportGenerator(llm, session)

        if body.report_kind == "fleet":
            content = await gen.generate_fleet_report()
        elif body.report_kind == "security":
            content = await gen.generate_security_report()
        else:
            content = await gen.generate_capacity_report()

        title = f"{body.report_kind.title()} Report — {now[:10]}"
    except Exception as exc:
        content = f"Report generation failed: {exc}"
        title = f"{body.report_kind.title()} Report (failed)"

    try:
        await session.execute(
            text("""
                INSERT INTO cognitive.report
                    (report_id, report_type, title, content_markdown, generated_by, created_at)
                VALUES (:rid, :rtype, :title, :content, :gen_by, :created)
            """),
            {
                "rid": report_id,
                "rtype": body.report_kind,
                "title": title,
                "content": content,
                "gen_by": "manual",
                "created": now,
            },
        )
        await session.commit()
    except Exception:
        logger.warning("Failed to persist report %s", report_id, exc_info=True)

    return ReportOut(
        report_id=report_id,
        report_kind=body.report_kind,
        title=title,
        content=content,
        generated_at=now,
        generated_by="manual",
    )


# ---------------------------------------------------------------------------
# Drift
# ---------------------------------------------------------------------------


class DriftCheckResponse(BaseModel):
    drift_id: str
    status: str
    entity_type: str
    entity_id: str | None = None
    message: str
    checked_at: str


@router.post(
    "/drift/check",
    response_model=DriftCheckResponse,
    dependencies=[Depends(require_role("operator", "platform_admin"))],
)
async def trigger_drift_check(
    body: DriftCheckRequest,
    _session: Annotated[AsyncSession, Depends(get_async_session)],
) -> DriftCheckResponse:
    """Trigger a configuration drift check."""
    drift_id = str(uuid.uuid4())
    return DriftCheckResponse(
        drift_id=drift_id,
        status="completed",
        entity_type=body.entity_type or "fleet",
        entity_id=body.entity_id,
        message="Drift check completed — no canonical baseline configured yet.",
        checked_at=_now_iso(),
    )


@router.get(
    "/drift/results",
    response_model=list[DriftResultOut],
    dependencies=[Depends(require_role("operator", "platform_admin", "viewer"))],
)
async def list_drift_results(
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> list[DriftResultOut]:
    """List active drift detections."""
    try:
        result = await session.execute(
            text("""
                SELECT * FROM cognitive.drift_result
                WHERE has_drift = true
                ORDER BY detected_at DESC
                LIMIT 100
            """),
        )
        return [DriftResultOut(**_row_to_dict(r)) for r in result.fetchall()]
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Self-Heal
# ---------------------------------------------------------------------------


@router.get(
    "/self-heal/history",
    response_model=list[SelfHealActionOut],
    dependencies=[Depends(require_role("operator", "platform_admin", "viewer"))],
)
async def self_heal_history(
    session: Annotated[AsyncSession, Depends(get_async_session)],
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> list[SelfHealActionOut]:
    """Self-healing action history."""
    try:
        offset = (page - 1) * page_size
        result = await session.execute(
            text("""
                SELECT * FROM cognitive.self_heal_action
                ORDER BY executed_at DESC
                LIMIT :limit OFFSET :offset
            """),
            {"limit": page_size, "offset": offset},
        )
        return [SelfHealActionOut(**_row_to_dict(r)) for r in result.fetchall()]
    except Exception:
        return []


@router.get(
    "/self-heal/playbooks",
    response_model=list[PlaybookOut],
    dependencies=[Depends(require_role("operator", "platform_admin", "viewer"))],
)
async def list_playbooks(
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> list[PlaybookOut]:
    """List available self-healing playbooks."""
    try:
        result = await session.execute(
            text("SELECT * FROM cognitive.playbook WHERE is_active = true ORDER BY name"),
        )
        return [PlaybookOut(**_row_to_dict(r)) for r in result.fetchall()]
    except Exception:
        return [
            PlaybookOut(
                playbook_id="pb-restart-service",
                name="Restart Unhealthy Service",
                description=(
                    "Automatically restarts a service container when health checks fail 3+ times."
                ),
                trigger_conditions=["health_check_fail_count >= 3"],
                risk_level="low",
            ),
            PlaybookOut(
                playbook_id="pb-clear-disk",
                name="Clear Temporary Files",
                description="Removes /tmp and log rotation when disk usage exceeds 90%.",
                trigger_conditions=["disk_usage_pct >= 90"],
                risk_level="low",
            ),
            PlaybookOut(
                playbook_id="pb-scale-up",
                name="Scale Up Replicas",
                description="Adds replicas when CPU usage sustains above 80% for 10 minutes.",
                trigger_conditions=["cpu_usage_pct >= 80", "duration >= 10m"],
                risk_level="medium",
            ),
        ]


# ---------------------------------------------------------------------------
# Agent Sessions (ReAct)
# ---------------------------------------------------------------------------


def _default_dict_list() -> list[dict[str, Any]]:
    """Typed default factory for list[dict[str, Any]] Pydantic fields.

    Using a named function instead of bare ``list`` as the default_factory prevents
    Pylance ``reportUnknownVariableType`` — ``list`` alone resolves as
    ``list[Unknown]`` because the builtin is not parameterised at call-site,
    and for nested generics (``list[dict[str, Any]]``) Pylance cannot narrow it.
    """
    return []


class AgentSessionOut(BaseModel):
    session_id: str
    goal: str = ""
    status: str = "running"
    model_used: str = "reasoning"
    iterations: int = 0
    tokens_used: int = 0
    tool_calls: list[dict[str, Any]] = Field(default_factory=_default_dict_list)
    conversation: list[dict[str, Any]] = Field(default_factory=_default_dict_list)
    final_answer: str | None = None
    error: str | None = None
    triggered_by: str = "cognitive_engine"
    created_at: str | None = None
    completed_at: str | None = None


def _row_to_agent_session(mapping: Any) -> AgentSessionOut:
    """Convert a raw SQLAlchemy ``RowMapping`` to :class:`AgentSessionOut`.

    Field-by-field assignment with explicit type coercions avoids the
    ``reportArgumentType`` Pylance diagnostic that fires when a dict
    comprehension producing ``Any | str`` is splatted (``**``) into a Pydantic
    constructor that expects typed parameters (``int``, ``list[dict[str,Any]]``).
    ``Any | str`` is not assignable to ``int`` under Pylance strict analysis
    because the ``str`` branch is visible; named-parameter callsites receive
    ``Any`` from direct dict-key access, which Pylance freely coerces.
    """

    def _iso(val: Any) -> str | None:
        """Return ISO-8601 string for datetime, plain str for other values, None for NULL."""
        if val is None:
            return None
        return val.isoformat() if hasattr(val, "isoformat") else str(val)

    return AgentSessionOut(
        session_id=str(mapping["session_id"]),
        goal=str(mapping["goal"] or ""),
        status=str(mapping["status"] or "running"),
        model_used=str(mapping["model_used"] or "reasoning"),
        iterations=int(mapping["iterations"] or 0),
        tokens_used=int(mapping["tokens_used"] or 0),
        tool_calls=cast(list[dict[str, Any]], mapping["tool_calls"] or []),
        conversation=cast(list[dict[str, Any]], mapping["conversation"] or []),
        final_answer=(
            str(mapping["final_answer"])
            if mapping["final_answer"] is not None
            else None
        ),
        error=(
            str(mapping["error"])
            if mapping["error"] is not None
            else None
        ),
        triggered_by=str(mapping["triggered_by"] or "cognitive_engine"),
        created_at=_iso(mapping["created_at"]),
        completed_at=_iso(mapping["completed_at"]),
    )


class StartAgentSessionRequest(BaseModel):
    goal: str = Field(min_length=1, max_length=2000)
    context: dict[str, Any] = Field(default_factory=dict)
    model_name: str = "reasoning"


@router.get(
    "/agent-sessions",
    response_model=list[AgentSessionOut],
    dependencies=[Depends(require_role("operator", "platform_admin"))],
)
async def list_agent_sessions(
    session: Annotated[AsyncSession, Depends(get_async_session)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> list[AgentSessionOut]:
    """List ReAct agent sessions ordered by most recent."""
    try:
        offset = (page - 1) * page_size
        result = await session.execute(
            text("""
                SELECT session_id, goal, status, model_used, iterations,
                       tokens_used, tool_calls, conversation, final_answer,
                       error, triggered_by, created_at, completed_at
                FROM cognitive.agent_session
                ORDER BY created_at DESC
                LIMIT :limit OFFSET :offset
            """),
            {"limit": page_size, "offset": offset},
        )
        rows = result.fetchall()
        return [_row_to_agent_session(r._mapping) for r in rows]
    except Exception as exc:
        logger.warning("Failed to list agent sessions: %s", exc)
        return []


@router.get(
    "/agent-sessions/{session_id}",
    response_model=AgentSessionOut,
    dependencies=[Depends(require_role("operator", "platform_admin"))],
)
async def get_agent_session(
    session_id: str,
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> AgentSessionOut:
    """Get a single agent session by ID."""
    result = await session.execute(
        text("""
            SELECT session_id, goal, status, model_used, iterations,
                   tokens_used, tool_calls, conversation, final_answer,
                   error, triggered_by, created_at, completed_at
            FROM cognitive.agent_session
            WHERE session_id = :sid
        """),
        {"sid": session_id},
    )
    row = result.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Agent session not found")
    return _row_to_agent_session(row._mapping)


@router.post(
    "/agent-sessions",
    response_model=AgentSessionOut,
    dependencies=[Depends(require_role("operator", "platform_admin"))],
)
async def start_agent_session(
    body: StartAgentSessionRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> AgentSessionOut:
    """Start a new ReAct agent session in the background.

    Returns immediately with ``status="running"`` and a ``session_id``.
    Stream live step events via ``GET /agent-sessions/{session_id}/stream``.
    """
    from internalcmdb.cognitive.agent_loop import AgentLoop  # noqa: PLC0415

    session_id = str(uuid.uuid4())
    user = getattr(request.state, "user_id", "api_user")
    now = _now_iso()

    # Pre-register the session so GET /agent-sessions/{id} works immediately
    await session.execute(
        text("""
            INSERT INTO cognitive.agent_session
                (session_id, goal, status, model_used, iterations, tokens_used,
                 tool_calls, conversation, triggered_by, created_at)
            VALUES
                (:sid, :goal, 'running', :model, 0, 0,
                 '[]'::json, '[]'::json, :tb, :created)
            ON CONFLICT (session_id) DO NOTHING
        """),
        {
            "sid": session_id,
            "goal": body.goal,
            "model": body.model_name or "reasoning",
            "tb": str(user),
            "created": now,
        },
    )
    await session.commit()

    async def _run_in_background() -> None:
        loop = AgentLoop(model_name=body.model_name)
        # Preserve the pre-assigned session_id
        loop._session_id_override = session_id  # type: ignore[attr-defined]
        await loop.run(body.goal, body.context, triggered_by=str(user))

    background_tasks.add_task(_run_in_background)

    return AgentSessionOut(
        session_id=session_id,
        goal=body.goal,
        status="running",
        model_used=body.model_name or "reasoning",
        iterations=0,
        tokens_used=0,
        tool_calls=[],
        conversation=[],
        triggered_by=str(user),
        created_at=now,
    )


# ---------------------------------------------------------------------------
# SSE helper
# ---------------------------------------------------------------------------

import asyncio as _asyncio  # noqa: E402
import json as _json  # noqa: E402

try:
    import redis.asyncio as _aioredis
except ImportError:
    _aioredis = None  # type: ignore[assignment]


def _is_done_event(data: str) -> bool:
    """Return True if the JSON payload contains ``phase: "done"``."""
    try:
        return bool(_json.loads(data).get("phase") == "done")
    except (_json.JSONDecodeError, AttributeError):
        return False


async def _sse_generator(session_id: str, redis_url: str, request: Request):  # type: ignore[return]
    """Async generator that yields SSE-formatted lines from Redis pubsub."""
    if _aioredis is None:
        raise RuntimeError("redis[asyncio] package is not installed")
    r: _AioRedis = _aioredis.from_url(redis_url, decode_responses=True)  # type: ignore[reportUnknownMemberType]
    pubsub: _AioPubSub = r.pubsub()  # type: ignore[reportUnknownMemberType]
    try:
        await pubsub.subscribe(f"infraq:agent:stream:{session_id}")  # type: ignore[reportUnknownMemberType]
        while not await request.is_disconnected():
            try:
                _get_coro = cast(
                    Awaitable[dict[str, Any] | None],
                    pubsub.get_message(  # type: ignore[reportUnknownMemberType]
                        ignore_subscribe_messages=True, timeout=1.0
                    ),
                )
                msg: dict[str, Any] | None = await _asyncio.wait_for(_get_coro, timeout=2.0)
            except TimeoutError:
                yield 'data: {"ping": true}\n\n'
                continue
            if msg is None:
                yield 'data: {"ping": true}\n\n'
                continue
            data = msg.get("data", "")
            if not isinstance(data, str):
                continue
            yield f"data: {data}\n\n"
            if _is_done_event(data):
                break
    finally:
        await pubsub.unsubscribe()  # type: ignore[reportUnknownMemberType]
        await r.aclose()


@router.get(
    "/agent-sessions/{session_id}/stream",
    dependencies=[Depends(require_role("operator", "platform_admin"))],
)
async def stream_agent_session(
    session_id: str,
    request: Request,
) -> StreamingResponse:
    """Server-Sent Events stream for a running agent session.

    Emits ``data: <json>\\n\\n`` for each ReAct step.
    The stream closes automatically when a ``phase="done"`` event arrives
    or when the client disconnects.
    """
    from internalcmdb.api.config import get_settings  # noqa: PLC0415

    settings = get_settings()
    return StreamingResponse(
        _sse_generator(session_id, settings.redis_url, request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post(
    "/agent-sessions/{session_id}/stop",
    response_model=AgentSessionOut,
    dependencies=[Depends(require_role("operator", "platform_admin"))],
)
async def stop_agent_session(
    session_id: str,
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> AgentSessionOut:
    """Force-stop a running agent session."""
    from datetime import UTC, datetime  # noqa: PLC0415

    row = await session.execute(
        text("""
            UPDATE cognitive.agent_session
            SET status = 'failed',
                error = 'Force-stopped by operator',
                completed_at = :now
            WHERE session_id = :sid AND status = 'running'
            RETURNING session_id, goal, status, model_used, iterations,
                      tokens_used, tool_calls, conversation, final_answer,
                      error, triggered_by, created_at, completed_at
        """),
        {"sid": session_id, "now": datetime.now(tz=UTC)},
    )
    result = row.mappings().first()
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"Session {session_id} not found or not running",
        )
    await session.commit()

    return AgentSessionOut(
        session_id=str(result["session_id"]),
        goal=result["goal"],
        status=result["status"],
        model_used=result["model_used"] or "reasoning",
        iterations=result["iterations"] or 0,
        tokens_used=result["tokens_used"] or 0,
        tool_calls=result["tool_calls"] or [],
        conversation=result["conversation"] or [],
        final_answer=result["final_answer"],
        error=result["error"],
        triggered_by=result["triggered_by"] or "unknown",
        created_at=str(result["created_at"]) if result["created_at"] else "",
        completed_at=str(result["completed_at"]) if result["completed_at"] else None,
    )


# ---------------------------------------------------------------------------
# Auto-Remediation trigger from insight
# ---------------------------------------------------------------------------


class RemediationResponse(BaseModel):
    session_id: str
    status: str


@router.post(
    "/insights/{insight_id}/remediate",
    response_model=RemediationResponse,
    dependencies=[Depends(require_role("operator", "platform_admin"))],
)
async def remediate_insight(
    insight_id: str,
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> RemediationResponse:
    """Trigger autonomous remediation for a specific insight via the ReAct agent."""
    # Fetch the insight for context
    result = await session.execute(
        text("""
            SELECT insight_id, entity_id, entity_type, severity, title,
                   description, remediation, category
            FROM cognitive.insight
            WHERE insight_id = :iid AND status = 'active'
        """),
        {"iid": insight_id},
    )
    row = result.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Insight not found or not active")

    insight = _row_to_dict(row)

    # Build goal from insight content
    goal = (
        f"Remediate the following issue on {insight.get('entity_type', 'entity')} "
        f"{insight.get('entity_id', 'unknown')}: {insight.get('title', '')}. "
        f"Description: {insight.get('description', '')}. "
        f"Suggested remediation: {insight.get('remediation', 'none')}."
    )

    from internalcmdb.cognitive.agent_loop import AgentLoop  # noqa: PLC0415

    loop = AgentLoop(model_name="reasoning")
    agent_result = await loop.run(
        goal,
        context={"insight_id": insight_id, **insight},
        triggered_by="auto_remediate",
    )

    # Mark the insight as being remediated
    await session.execute(
        text("""
            UPDATE cognitive.insight
            SET status = 'remediating', updated_at = NOW()
            WHERE insight_id = :iid
        """),
        {"iid": insight_id},
    )
    await session.commit()

    return RemediationResponse(
        session_id=agent_result.session_id,
        status=agent_result.status,
    )


# ---------------------------------------------------------------------------
# Knowledge-base manual ingest
# ---------------------------------------------------------------------------


class KBIngestResponse(BaseModel):
    status: str
    counts: dict[str, int]


@router.post(
    "/knowledge-base/ingest",
    response_model=KBIngestResponse,
    dependencies=[Depends(require_role("platform_admin"))],
)
async def trigger_kb_ingest(
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> KBIngestResponse:
    """Trigger a synchronous knowledge-base ingest from all data sources.

    Reserved for ``platform_admin`` role.  Prefer the ARQ cron for routine
    ingestion; use this endpoint to force an immediate refresh.
    """
    from internalcmdb.cognitive.kb_ingestor import KnowledgeBaseIngestor  # noqa: PLC0415
    from internalcmdb.llm.client import LLMClient  # noqa: PLC0415

    async with LLMClient() as llm:
        ingestor = KnowledgeBaseIngestor()
        counts = await ingestor.ingest_all(session, llm)

    return KBIngestResponse(status="ok", counts=counts)
