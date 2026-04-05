"""Tests for observability.tracing — setup_tracing, record_llm_span_attributes."""
from __future__ import annotations
from unittest.mock import MagicMock


def test_setup_tracing_no_error_without_otel():
    from internalcmdb.observability.tracing import setup_tracing
    result = setup_tracing(service_name="test")


def test_setup_tracing_with_grpc_endpoint():
    from internalcmdb.observability.tracing import setup_tracing
    setup_tracing(service_name="test", otlp_endpoint="http://localhost:4317", otlp_protocol="grpc")


def test_setup_tracing_with_http_endpoint():
    from internalcmdb.observability.tracing import setup_tracing
    setup_tracing(service_name="test", otlp_endpoint="http://localhost:4318", otlp_protocol="http")


def test_setup_tracing_importable():
    from internalcmdb.observability import tracing
    assert hasattr(tracing, "setup_tracing")
    assert hasattr(tracing, "record_llm_span_attributes")


def test_record_llm_span_attributes_with_mock_span():
    from internalcmdb.observability.tracing import record_llm_span_attributes
    mock_span = MagicMock()
    record_llm_span_attributes(
        mock_span,
        model="test-model",
        input_tokens=10,
        output_tokens=20,
    )
    assert mock_span.set_attribute.called


def test_record_llm_span_attributes_none_span():
    from internalcmdb.observability.tracing import record_llm_span_attributes
    record_llm_span_attributes(None, model="test-model", input_tokens=0, output_tokens=0)


def test_record_llm_span_attributes_finish_reasons():
    from internalcmdb.observability.tracing import record_llm_span_attributes
    mock_span = MagicMock()
    record_llm_span_attributes(mock_span, model="test", finish_reasons=["stop"])
    calls = [str(c) for c in mock_span.set_attribute.call_args_list]
    assert any("finish_reasons" in c for c in calls)
