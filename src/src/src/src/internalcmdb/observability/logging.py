"""F7.1 — Structured Logging: JSON formatter with correlation-ID propagation.

Configures Python's ``logging`` module to emit JSON-structured log records in
production and Rich-formatted output in development mode.  A ``ContextVar``
carries the ``correlation_id`` across async task boundaries so every log line
within a single request/transaction can be grouped.

Integration::

    # In main.py lifespan:
    from internalcmdb.observability.logging import setup_logging
    setup_logging(log_format="json")  # or "rich" for dev
"""

from __future__ import annotations

import json
import logging
import sys
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any, ClassVar

correlation_id_var: ContextVar[str | None] = ContextVar("correlation_id", default=None)

_SERVICE_NAME = "internalcmdb"


_MAX_EXTRA_SIZE = 8192  # truncate oversized extra payloads


class JSONFormatter(logging.Formatter):
    """Emits one JSON object per log record.

    Fields: timestamp, level, correlation_id, service, module, event_type,
    message, extra.
    """

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict[str, Any] = {
            "timestamp": datetime.now(tz=UTC).isoformat(),
            "level": record.levelname,
            "correlation_id": correlation_id_var.get(),
            "service": _SERVICE_NAME,
            "module": record.name,
            "event_type": getattr(record, "event_type", None),
            "message": record.getMessage(),
        }

        extra = {
            k: v
            for k, v in record.__dict__.items()
            if k not in _BUILTIN_LOG_ATTRS and not k.startswith("_")
        }
        if extra:
            log_entry["extra"] = _truncate_extra(extra)

        if record.exc_info and record.exc_info[1] is not None:
            log_entry["exception"] = self.formatException(record.exc_info)

        try:
            return json.dumps(log_entry, default=str)
        except ValueError, TypeError, OverflowError:
            log_entry.pop("extra", None)
            log_entry["_format_error"] = True
            return json.dumps(log_entry, default=str)


def _truncate_extra(extra: dict[str, Any]) -> dict[str, Any]:
    """Prevent oversized extra payloads from bloating log lines."""
    serialised = json.dumps(extra, default=str)
    if len(serialised) <= _MAX_EXTRA_SIZE:
        return extra
    return {"_truncated": True, "_original_size": len(serialised), "_keys": list(extra.keys())[:20]}


_BUILTIN_LOG_ATTRS = frozenset(
    {
        "name",
        "msg",
        "args",
        "created",
        "relativeCreated",
        "exc_info",
        "exc_text",
        "stack_info",
        "lineno",
        "funcName",
        "pathname",
        "filename",
        "module",
        "levelno",
        "levelname",
        "processName",
        "process",
        "threadName",
        "thread",
        "msecs",
        "message",
        "event_type",
        "taskName",
    }
)


class _DevFormatter(logging.Formatter):
    """Coloured single-line formatter for development (no Rich dependency)."""

    _COLORS: ClassVar[dict[str, str]] = {
        "DEBUG": "\033[36m",  # cyan
        "INFO": "\033[32m",  # green
        "WARNING": "\033[33m",  # yellow
        "ERROR": "\033[31m",  # red
        "CRITICAL": "\033[41m",  # red bg
    }
    _RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        color = self._COLORS.get(record.levelname, "")
        cid = correlation_id_var.get() or "-"
        ts = datetime.now(tz=UTC).strftime("%H:%M:%S.%f")[:-3]
        base = (
            f"{color}{ts} {record.levelname:8s}{self._RESET} "
            f"[{cid[:8]}] {record.name}: {record.getMessage()}"
        )
        extra = {
            k: v
            for k, v in record.__dict__.items()
            if k not in _BUILTIN_LOG_ATTRS and not k.startswith("_")
        }
        if extra:
            items = " ".join(f"{k}={v!r}" for k, v in list(extra.items())[:10])
            base += f" | {items}"
        if record.exc_info and record.exc_info[1] is not None:
            base += "\n" + self.formatException(record.exc_info)
        return base


_VALID_LEVELS = frozenset({"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"})


def setup_logging(
    log_format: str = "json",
    level: str = "INFO",
) -> None:
    """Configure the root logger for the application.

    Args:
        log_format: ``"json"`` for production, ``"dev"`` for coloured console.
        level: Root log level (e.g. ``"DEBUG"``, ``"INFO"``).
    """
    resolved_level = level.upper()
    if resolved_level not in _VALID_LEVELS:
        resolved_level = "INFO"
        logging.getLogger(__name__).warning(
            "Invalid log level %r — falling back to INFO",
            level,
        )

    root = logging.getLogger()
    root.setLevel(getattr(logging, resolved_level))

    for handler in root.handlers[:]:
        root.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)

    if log_format == "json":
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(_DevFormatter())

    root.addHandler(handler)

    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def set_correlation_id(cid: str | None) -> None:
    """Set the correlation ID for the current async context."""
    correlation_id_var.set(cid)


def get_correlation_id() -> str | None:
    """Retrieve the current correlation ID."""
    return correlation_id_var.get()
