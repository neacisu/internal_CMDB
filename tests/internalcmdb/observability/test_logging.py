"""Tests for observability.logging."""
from __future__ import annotations
import json
import logging
from internalcmdb.observability.logging import (
    JSONFormatter, _DevFormatter, get_correlation_id, set_correlation_id, setup_logging
)


def _record(msg="test", level=logging.INFO):
    return logging.LogRecord("test.logger", level, "test.py", 1, msg, (), None)


def test_set_get_correlation_id():
    set_correlation_id("corr-001")
    assert get_correlation_id() == "corr-001"


def test_set_correlation_id_none():
    set_correlation_id(None)
    assert get_correlation_id() is None


def test_json_formatter_valid_json():
    f = JSONFormatter()
    data = json.loads(f.format(_record()))
    assert data["message"] == "test" and data["level"] == "INFO"


def test_json_formatter_correlation_id():
    set_correlation_id("test-xyz")
    data = json.loads(JSONFormatter().format(_record()))
    assert data["correlation_id"] == "test-xyz"
    set_correlation_id(None)


def test_json_formatter_exception():
    import sys
    try:
        raise ValueError("test error")
    except ValueError:
        exc_info = sys.exc_info()
    r = _record()
    r.exc_info = exc_info
    data = json.loads(JSONFormatter().format(r))
    assert "exception" in data and "ValueError" in data["exception"]


def test_json_formatter_extra_fields():
    r = _record()
    r.custom_field = "custom_value"
    data = json.loads(JSONFormatter().format(r))
    assert "extra" in data


def test_json_formatter_oversized_extra():
    r = _record()
    r.big_data = "x" * 10000
    data = json.loads(JSONFormatter().format(r))
    extra = data.get("extra", {})
    assert "_truncated" in extra or "big_data" in extra


def test_dev_formatter_produces_string():
    out = _DevFormatter().format(_record())
    assert "test" in out and isinstance(out, str)


def test_dev_formatter_includes_extra():
    r = _record()
    r.host_code = "hz-01"
    assert "host_code" in _DevFormatter().format(r)


def test_setup_logging_json():
    setup_logging(log_format="json", level="DEBUG")
    root = logging.getLogger()
    assert root.level == logging.DEBUG
    assert any(isinstance(h.formatter, JSONFormatter) for h in root.handlers)


def test_setup_logging_dev():
    setup_logging(log_format="dev", level="INFO")
    root = logging.getLogger()
    assert any(isinstance(h.formatter, _DevFormatter) for h in root.handlers)


def test_setup_logging_invalid_level():
    setup_logging(log_format="json", level="NOTVALID")
    assert logging.getLogger().level == logging.INFO


def test_setup_logging_replaces_handlers():
    setup_logging(log_format="json")
    setup_logging(log_format="dev")
    assert len(logging.getLogger().handlers) == 1
