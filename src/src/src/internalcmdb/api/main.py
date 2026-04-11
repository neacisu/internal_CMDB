"""FastAPI application entry point."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from .config import get_settings
from .routers import (
    agent,
    agent_commands,
    audit,
    cognitive,
    collectors,
    compliance,
    dashboard,
    debug,
    discovery,
    documents,
    governance,
    graph,
    hitl,
    metrics_live,
    realtime,
    registry,
    results,
    retrieval,
    slo,
    workers,
)
from .routers import (
    auth as auth_router,
)
from .routers import (
    settings as settings_router,
)

logger = logging.getLogger("internalcmdb.staleness")

_STALENESS_INTERVAL = 30  # seconds between automatic staleness sweeps
_ESCALATION_CHECK_INTERVAL = 60  # seconds between HITL escalation checks


async def _staleness_loop() -> None:
    """Run the agent staleness checker automatically every 30 seconds."""
    from internalcmdb.api.deps import _get_session_factory  # noqa: PLC0415
    from internalcmdb.collectors.staleness import check_staleness  # noqa: PLC0415

    await asyncio.sleep(5)
    while True:
        try:
            factory = _get_session_factory()
            db = factory()
            try:
                counts = await asyncio.to_thread(check_staleness, db)
                if any(counts.values()):
                    logger.info("Staleness sweep: %s", counts)
            finally:
                db.close()
        except Exception:
            logger.exception("Staleness sweep failed")
        await asyncio.sleep(_STALENESS_INTERVAL)


async def _escalation_loop() -> None:
    """Periodically check for HITL items that need auto-escalation."""
    from internalcmdb.api.deps import _get_async_session_factory  # noqa: PLC0415
    from internalcmdb.governance.hitl_workflow import HITLWorkflow  # noqa: PLC0415

    await asyncio.sleep(10)
    while True:
        try:
            factory = _get_async_session_factory()
            async with factory() as session:
                wf = HITLWorkflow(session)
                count = await wf.check_escalations()
                if count:
                    logger.info("HITL escalation sweep: %d items escalated", count)
        except Exception:
            logger.exception("HITL escalation sweep failed")
        await asyncio.sleep(_ESCALATION_CHECK_INTERVAL)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Startup / shutdown hook — validates config and starts background tasks."""
    settings = get_settings()  # validates .env on startup

    from internalcmdb.models.retrieval import _EMBEDDING_DIM  # noqa: PLC0415
    from internalcmdb.observability.logging import setup_logging  # noqa: PLC0415
    from internalcmdb.observability.tracing import setup_tracing  # noqa: PLC0415

    if settings.embedding_vector_dim != _EMBEDDING_DIM:
        raise RuntimeError(
            f"EMBEDDING_VECTOR_DIM mismatch: Settings={settings.embedding_vector_dim}, "
            f"model={_EMBEDDING_DIM}.  Both must read the same EMBEDDING_VECTOR_DIM env var."
        )

    setup_logging(log_format=settings.log_format, level=settings.log_level)
    provider = setup_tracing(
        "internalcmdb",
        otlp_endpoint=settings.otlp_endpoint,
        otlp_protocol=settings.otlp_protocol,
        otlp_insecure=settings.otlp_insecure,
        sample_rate=settings.otel_sample_rate,
    )

    # Inject JWT_SECRET_KEY from SecretProvider into the process environment
    # so that auth/security.py can read it synchronously via os.environ.
    import os  # noqa: PLC0415

    from internalcmdb.config.secrets import SecretProvider  # noqa: PLC0415

    _provider = SecretProvider()
    _jwt_secret = await _provider.get("JWT_SECRET_KEY")
    if not _jwt_secret or len(_jwt_secret) < 32:  # noqa: PLR2004
        raise RuntimeError(
            "JWT_SECRET_KEY must be set and at least 32 characters long. "
            "Configure it in the secrets backend."
        )
    os.environ["JWT_SECRET_KEY"] = _jwt_secret

    staleness_task = asyncio.create_task(_staleness_loop())
    escalation_task = asyncio.create_task(_escalation_loop())
    try:
        yield
    finally:
        staleness_task.cancel()
        escalation_task.cancel()
        await asyncio.gather(staleness_task, escalation_task, return_exceptions=True)

        from internalcmdb.api.deps import dispose_engines  # noqa: PLC0415

        await dispose_engines()

        if provider is not None:
            provider.force_flush()
            provider.shutdown()


def create_app() -> FastAPI:
    settings = get_settings()

    fapp = FastAPI(
        title="internalCMDB API",
        description=(
            "Enterprise infrastructure registry, discovery, governance, "
            "cognitive brain, and worker management API."
        ),
        version="1.0.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
        openapi_tags=[
            {
                "name": "settings",
                "description": (
                    "Runtime configuration management — LLM backends, budgets, guard, "
                    "HITL, retention, observability, notifications, user preferences"
                ),
            },
            {
                "name": "cognitive",
                "description": (
                    "Cognitive brain \u2014 NL queries, insights, health scores, drift, reports"
                ),
            },
            {"name": "hitl", "description": "Human-In-The-Loop review queue, decisions, accuracy"},
            {"name": "metrics", "description": "Live fleet metrics and Prometheus exposition"},
            {"name": "realtime", "description": "WebSocket and SSE real-time data streams"},
            {"name": "debug", "description": "Debug traces, LLM calls, guard blocks"},
            {"name": "registry", "description": "Host, cluster, service, GPU registry"},
            {"name": "discovery", "description": "Collection runs, observed facts, evidence"},
            {"name": "governance", "description": "Policies, approvals, changelog"},
            {"name": "retrieval", "description": "Document chunks and evidence packs"},
            {"name": "collectors", "description": "Agent enrollment, telemetry, fleet health"},
            {"name": "dashboard", "description": "Aggregated dashboard statistics"},
            {"name": "workers", "description": "Script execution, jobs, schedules"},
            {"name": "results", "description": "Subproject audit results"},
            {"name": "documents", "description": "Documentation index and content"},
            {"name": "slo", "description": "Service Level Objectives and error budgets"},
            {"name": "compliance", "description": "Compliance frameworks and checks"},
            {"name": "graph", "description": "Dependency graph and topology"},
            {"name": "meta", "description": "Health checks and metadata"},
        ],
    )

    from slowapi.errors import RateLimitExceeded  # noqa: PLC0415

    from .middleware.audit import AuditMiddleware  # noqa: PLC0415
    from .middleware.rate_limit import limiter, rate_limit_exceeded_handler  # noqa: PLC0415

    fapp.state.limiter = limiter
    fapp.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)  # type: ignore[arg-type]

    origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
    fapp.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    fapp.add_middleware(AuditMiddleware)

    from starlette.middleware.base import BaseHTTPMiddleware  # noqa: PLC0415

    class _SecurityHeadersMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):  # type: ignore[override]
            response = await call_next(request)
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
            return response

    fapp.add_middleware(_SecurityHeadersMiddleware)

    prefix = "/api/v1"
    fapp.include_router(auth_router.router, prefix=prefix)
    fapp.include_router(registry.router, prefix=prefix)
    fapp.include_router(discovery.router, prefix=prefix)
    fapp.include_router(governance.router, prefix=prefix)
    fapp.include_router(audit.router, prefix=prefix)
    fapp.include_router(retrieval.router, prefix=prefix)
    fapp.include_router(agent.router, prefix=prefix)
    fapp.include_router(agent_commands.router, prefix=prefix)
    fapp.include_router(collectors.router, prefix=prefix)
    fapp.include_router(dashboard.router, prefix=prefix)
    fapp.include_router(workers.router, prefix=prefix)
    fapp.include_router(results.router, prefix=prefix)
    fapp.include_router(documents.router, prefix=prefix)
    fapp.include_router(hitl.router, prefix=prefix)
    fapp.include_router(cognitive.router, prefix=prefix)
    fapp.include_router(metrics_live.router, prefix=prefix)

    if settings.debug_enabled:
        fapp.include_router(debug.router, prefix=prefix)

    fapp.include_router(compliance.router, prefix=prefix)

    fapp.include_router(graph.router, prefix=prefix)
    fapp.include_router(slo.router, prefix=prefix)
    fapp.include_router(settings_router.router, prefix=prefix)

    # Real-time WebSocket + SSE (mounted at /api/v1/ for consistency)
    fapp.include_router(realtime.router, prefix=prefix)

    @fapp.get("/health", tags=["meta"])
    def health() -> dict[str, Any]:  # pyright: ignore[reportUnusedFunction]
        return {"status": "ok", "log_level": settings.log_level}

    @fapp.get("/metrics", tags=["meta"], include_in_schema=False)
    def metrics() -> Response:  # pyright: ignore[reportUnusedFunction]
        import internalcmdb.observability.metrics as _  # noqa: F401,PLC0415

        return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

    return fapp


app = create_app()
