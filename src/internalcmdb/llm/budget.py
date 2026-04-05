"""Token Budget Manager (Phase 14, F14).

Enforces per-caller hourly token budgets to prevent runaway LLM costs
and detect usage spikes indicative of prompt-injection loops or
misconfigured automation.

Features:
    - Per-caller rolling 1-hour budget windows
    - Default 100k tokens/hour per caller
    - Spike detection: alert if usage exceeds 3x rolling average
    - Process-safe usage tracking under concurrent async tasks (``asyncio.Lock``)

Public surface::

    from internalcmdb.llm.budget import TokenBudgetManager

    mgr = TokenBudgetManager()
    ok = await mgr.check_budget("agent-audit", 5000)
    await mgr.record_usage("agent-audit", 5000)
    stats = await mgr.get_usage_stats()
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_BUDGET = 100_000
_WINDOW_SECONDS = 3600
_SPIKE_MULTIPLIER = 3.0
_SPIKE_MIN_SAMPLES = 5


# ---------------------------------------------------------------------------
# Usage record for spike detection
# ---------------------------------------------------------------------------


@dataclass
class _UsageRecord:
    """Single usage record for a caller."""

    tokens: int
    timestamp: float


@dataclass
class _BudgetEntry:
    """Per-caller budget tracking state."""

    used: int = 0
    limit: int = _DEFAULT_BUDGET
    window_start: float = 0.0
    history: deque[_UsageRecord] = field(default_factory=lambda: deque(maxlen=100))


# ---------------------------------------------------------------------------
# Token Budget Manager
# ---------------------------------------------------------------------------


class TokenBudgetManager:
    """Manages per-caller token budgets with spike detection.

    Callers are identified by string IDs (e.g. ``"agent-audit"``,
    ``"cognitive-query"``).  Each caller gets a configurable hourly
    budget (default 100k tokens).
    """

    CUSTOM_BUDGETS: dict[str, int] = {
        "agent-audit": 200_000,
        "agent-capacity": 150_000,
        "agent-security": 100_000,
        "cognitive-query": 50_000,
        "report-generator": 300_000,
        "chaos-engine": 30_000,
    }

    def __init__(self) -> None:
        self._budgets: dict[str, _BudgetEntry] = {}
        self._lock = asyncio.Lock()

    async def reload_from_settings(self) -> None:
        """Reload per-caller limits from SettingsStore.

        Existing in-flight usage counters are preserved; only the *limit*
        field is updated so the next window picks up the new cap.
        """
        try:
            from internalcmdb.config.settings_store import get_settings_store  # noqa: PLC0415
            store = get_settings_store()
            callers = list(self.CUSTOM_BUDGETS) + ["default"]
            async with self._lock:
                for caller in callers:
                    key = f"budget.{caller.replace('-', '_')}"
                    val = await store.get(key)
                    if val is not None:
                        new_limit = int(val)
                        self.CUSTOM_BUDGETS[caller] = new_limit
                        entry = self._budgets.get(caller)
                        if entry is not None:
                            entry.limit = new_limit
            logger.debug("TokenBudgetManager: reloaded limits from SettingsStore")
        except Exception:  # noqa: BLE001
            logger.warning("TokenBudgetManager: reload_from_settings failed; keeping existing limits")

    def _get_or_create(self, caller: str) -> _BudgetEntry:
        """Get or create a budget entry for the given caller."""
        now = time.monotonic()

        entry = self._budgets.get(caller)
        if entry is None:
            limit = self.CUSTOM_BUDGETS.get(caller, _DEFAULT_BUDGET)
            entry = _BudgetEntry(used=0, limit=limit, window_start=now)
            self._budgets[caller] = entry
            return entry

        if now - entry.window_start > _WINDOW_SECONDS:
            entry.used = 0
            entry.window_start = now

        return entry

    # ------------------------------------------------------------------
    # Budget check
    # ------------------------------------------------------------------

    async def check_budget(self, caller: str, tokens: int) -> bool:
        """Check whether *caller* can consume *tokens* within the current window.

        Does NOT record usage — call :meth:`record_usage` after the LLM
        call completes to debit the actual tokens consumed.

        Serialized with :class:`asyncio.Lock` so concurrent FastAPI tasks do not
        corrupt per-caller counters.
        """
        async with self._lock:
            entry = self._get_or_create(caller)

            if entry.used + tokens > entry.limit:
                logger.warning(
                    "Budget check DENIED for %s: %d + %d > %d (window started %.0fs ago)",
                    caller,
                    entry.used,
                    tokens,
                    entry.limit,
                    time.monotonic() - entry.window_start,
                )
                return False

            return True

    # ------------------------------------------------------------------
    # Usage recording
    # ------------------------------------------------------------------

    async def record_usage(self, caller: str, tokens: int) -> None:
        """Record *tokens* consumed by *caller* and check for spikes."""
        async with self._lock:
            entry = self._get_or_create(caller)
            entry.used += tokens

            now = time.monotonic()
            entry.history.append(_UsageRecord(tokens=tokens, timestamp=now))

            self._check_spike(caller, entry, tokens)

    # ------------------------------------------------------------------
    # Spike detection
    # ------------------------------------------------------------------

    def _check_spike(
        self, caller: str, entry: _BudgetEntry, current_tokens: int
    ) -> None:
        """Alert if the current usage is > 3x the rolling average."""
        now = time.monotonic()
        recent = [
            r for r in entry.history
            if now - r.timestamp <= _WINDOW_SECONDS
        ]

        if len(recent) < _SPIKE_MIN_SAMPLES:
            return

        avg = sum(r.tokens for r in recent) / len(recent)

        if avg > 0 and current_tokens > avg * _SPIKE_MULTIPLIER:
            logger.warning(
                "TOKEN SPIKE detected for %s: current=%d avg=%.0f (%.1fx)",
                caller,
                current_tokens,
                avg,
                current_tokens / avg,
            )

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    async def get_usage_stats(self) -> dict[str, Any]:
        """Return usage statistics for all known callers."""
        async with self._lock:
            now = time.monotonic()
            stats: dict[str, Any] = {
                "timestamp": datetime.now(tz=UTC).isoformat(),
                "callers": {},
            }

            for caller, entry in self._budgets.items():
                window_age = now - entry.window_start
                recent = [r for r in entry.history if now - r.timestamp <= _WINDOW_SECONDS]
                recent_total = sum(r.tokens for r in recent)

                stats["callers"][caller] = {
                    "used": entry.used,
                    "limit": entry.limit,
                    "remaining": max(0, entry.limit - entry.used),
                    "utilization_pct": (
                        round(entry.used / entry.limit * 100, 1) if entry.limit else 0
                    ),
                    "window_age_seconds": round(window_age),
                    "requests_in_window": len(recent),
                    "tokens_in_window": recent_total,
                    "avg_tokens_per_request": (
                        round(recent_total / len(recent)) if recent else 0
                    ),
                }

            return stats
