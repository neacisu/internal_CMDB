"""F7.2 — OpenTelemetry: distributed tracing for FastAPI, httpx, and SQLAlchemy.

Sets up an OTLP exporter with custom GenAI span attributes for LLM call
observability.  Instruments FastAPI (auto), httpx (for LLM backend calls),
and SQLAlchemy.

Integration::

    # In main.py lifespan:
    from internalcmdb.observability.tracing import setup_tracing
    setup_tracing("internalcmdb", otlp_endpoint="http://otel-collector:4317")
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def setup_tracing(
    service_name: str = "internalcmdb",
    *,
    otlp_endpoint: str = "http://localhost:4317",
    otlp_protocol: str = "grpc",
    otlp_insecure: bool = True,
    sample_rate: float = 1.0,
) -> Any:
    """Initialise the OpenTelemetry SDK with OTLP export and auto-instrumentation.

    Returns the configured ``TracerProvider`` (or ``None`` if OTel SDK is not
    installed).  Gracefully degrades when dependencies are missing — the
    application still runs, just without tracing.

    Args:
        otlp_protocol: ``"grpc"`` (default) or ``"http"`` for HTTP/protobuf.
        otlp_insecure: ``False`` to require TLS on the exporter connection.
        sample_rate: 0.0–1.0 ratio-based sampling (1.0 = trace everything).
    """
    try:
        from opentelemetry import trace  # noqa: PLC0415
        from opentelemetry.sdk.resources import Resource  # noqa: PLC0415
        from opentelemetry.sdk.trace import TracerProvider  # noqa: PLC0415
        from opentelemetry.sdk.trace.export import BatchSpanProcessor  # noqa: PLC0415
        from opentelemetry.sdk.trace.sampling import (  # noqa: PLC0415
            DEFAULT_ON,
            TraceIdRatioBased,
        )
    except ImportError:
        logger.info("OpenTelemetry SDK not installed — tracing disabled")
        return None

    sampler = DEFAULT_ON if sample_rate >= 1.0 else TraceIdRatioBased(max(0.0, min(sample_rate, 1.0)))

    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource, sampler=sampler)

    exporter = _create_exporter(otlp_endpoint, otlp_protocol, otlp_insecure)
    if exporter is None:
        logger.warning("Could not create OTLP exporter — tracing disabled")
        return None

    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    _instrument_fastapi()
    _instrument_httpx()
    _instrument_sqlalchemy()

    logger.info(
        "OpenTelemetry tracing enabled: service=%s endpoint=%s protocol=%s sample_rate=%.2f",
        service_name, otlp_endpoint, otlp_protocol, sample_rate,
    )
    return provider


def _create_exporter(endpoint: str, protocol: str, insecure: bool) -> Any:
    """Create the appropriate OTLP exporter based on protocol selection."""
    if protocol == "http":
        try:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import (  # noqa: PLC0415
                OTLPSpanExporter as HTTPExporter,
            )
            return HTTPExporter(endpoint=endpoint)
        except ImportError:
            logger.warning("opentelemetry-exporter-otlp-proto-http not installed, trying gRPC")

    try:
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (  # noqa: PLC0415
            OTLPSpanExporter as GRPCExporter,
        )
        return GRPCExporter(endpoint=endpoint, insecure=insecure)
    except ImportError:
        logger.error("No OTLP exporter package installed (grpc or http)")
        return None


def record_llm_span_attributes(
    span: Any,
    *,
    system: str = "vllm",
    model: str = "",
    input_tokens: int = 0,
    output_tokens: int = 0,
    finish_reasons: list[str] | None = None,
) -> None:
    """Set GenAI semantic convention attributes on an OTel span.

    These follow the emerging ``gen_ai.*`` attribute namespace used by
    the OpenTelemetry GenAI working group.
    """
    if span is None:
        return
    try:
        span.set_attribute("gen_ai.system", system)
        if model:
            span.set_attribute("gen_ai.request.model", model)
        if input_tokens:
            span.set_attribute("gen_ai.usage.input_tokens", input_tokens)
        if output_tokens:
            span.set_attribute("gen_ai.usage.output_tokens", output_tokens)
        if finish_reasons:
            span.set_attribute("gen_ai.response.finish_reasons", finish_reasons)
    except Exception:
        logger.debug("Failed to set GenAI span attributes", exc_info=True)


def _instrument_fastapi() -> None:
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor  # noqa: PLC0415

        FastAPIInstrumentor().instrument()
        logger.debug("FastAPI auto-instrumentation enabled")
    except ImportError:
        logger.debug("opentelemetry-instrumentation-fastapi not installed")


def _instrument_httpx() -> None:
    try:
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor  # noqa: PLC0415

        HTTPXClientInstrumentor().instrument()
        logger.debug("httpx instrumentation enabled")
    except ImportError:
        logger.debug("opentelemetry-instrumentation-httpx not installed")


def _instrument_sqlalchemy() -> None:
    try:
        from opentelemetry.instrumentation.sqlalchemy import (  # noqa: PLC0415
            SQLAlchemyInstrumentor,
        )

        SQLAlchemyInstrumentor().instrument()
        logger.debug("SQLAlchemy instrumentation enabled")
    except ImportError:
        logger.debug("opentelemetry-instrumentation-sqlalchemy not installed")
