"""F1.4 — Reactive Loop: sensor→cortex→motor event processing pipeline.

Implements the nervous-system pattern where incoming sensor events are
routed through anomaly detection and risk-class-based decision gates.

Event flow:
  sensor:ingest  →  cortex:anomaly  (placeholder for FactAnalyzer)
  cortex:anomaly →  risk-class routing:
      RC-1 (read-only)               →  motor:action          (auto-execute)
      RC-2 (agent draft/human approve) →  immune:hitl          (1 approver)
      RC-3 (supervised write)         →  immune:hitl            (2 approvers)
      RC-4 (bulk structural)          →  consciousness:alert   (block + alert)

Risk classes are sourced from ``internalcmdb.retrieval.task_types.RiskClass``
and align with the policy matrix in ``internalcmdb.control.policy_matrix``.

Consumer group semantics follow Redis Streams conventions:
  group:    reactor-group
  consumer: reactor-{hostname}

Usage::

    loop = ReactiveLoop(event_bus, guard_pipeline)
    await loop.run()        # blocks until shutdown
    loop.request_shutdown() # from another coroutine or signal handler
"""

from __future__ import annotations

import asyncio
import logging
import platform
import time
from collections import OrderedDict
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from internalcmdb.nervous.event_bus import Event, EventBus
from internalcmdb.retrieval.task_types import RiskClass

if TYPE_CHECKING:
    from internalcmdb.llm.guard import GuardPipeline

logger = logging.getLogger(__name__)

_HOSTNAME = platform.node() or "unknown"

CONSUMER_GROUP = "reactor-group"
CONSUMER_NAME = f"reactor-{_HOSTNAME}"

STREAM_SENSOR_INGEST = "sensor:ingest"
STREAM_CORTEX_ANOMALY = "cortex:anomaly"
STREAM_MOTOR_ACTION = "motor:action"
STREAM_IMMUNE_HITL = "immune:hitl"
STREAM_CONSCIOUSNESS_ALERT = "consciousness:alert"

_RISK_CLASS_APPROVAL_MAP: dict[RiskClass, int] = {
    RiskClass.RC2_AGENT_DRAFT_HUMAN_APPROVE: 1,
    RiskClass.RC3_SUPERVISED_WRITE: 2,
}

_DEDUP_MAX_SIZE = 10_000
_DEDUP_TTL_SECONDS = 300.0


class ReactiveLoop:
    """Main reactive event loop — subscribes to sensor:ingest and routes events.

    Args:
        event_bus:      An :class:`EventBus` implementation.
        guard_pipeline: A :class:`GuardPipeline` instance (F1.3) for guarded
                        LLM calls within the anomaly analysis path.
    """

    def __init__(self, event_bus: EventBus, guard_pipeline: GuardPipeline) -> None:
        self._bus = event_bus
        self._guard = guard_pipeline
        self._shutdown = asyncio.Event()
        self._processed_ids: OrderedDict[str, float] = OrderedDict()
        self.stats_processed: int = 0
        self.stats_duplicates: int = 0
        self.stats_errors: int = 0

    def request_shutdown(self) -> None:
        """Signal the reactor to exit its main loop gracefully."""
        self._shutdown.set()

    @property
    def is_running(self) -> bool:
        return not self._shutdown.is_set()

    async def run(self) -> None:
        """Main loop — reads from ``sensor:ingest`` until shutdown is requested.

        Individual event failures are logged but do not crash the loop.
        """
        logger.info(
            "reactor.start | group=%s consumer=%s stream=%s",
            CONSUMER_GROUP, CONSUMER_NAME, STREAM_SENSOR_INGEST,
        )

        while not self._shutdown.is_set():
            try:
                events = await self._bus.subscribe(
                    stream=STREAM_SENSOR_INGEST,
                    group=CONSUMER_GROUP,
                    consumer=CONSUMER_NAME,
                    count=10,
                    block_ms=2000,
                )
            except Exception:
                self.stats_errors += 1
                logger.exception("reactor.subscribe.error — retrying in 5s")
                await self._sleep_or_shutdown(5.0)
                continue

            for event in events:
                await self._handle_event_safely(event)

        logger.info("reactor.shutdown | consumer=%s", CONSUMER_NAME)

    async def _handle_event_safely(self, event: Event) -> None:
        """Process a single event with deduplication and safe ACK."""
        if self._is_duplicate(event.event_id):
            self.stats_duplicates += 1
            logger.info("reactor.dedup.skip | event_id=%s", event.event_id)
            if event.redis_message_id:
                await self._safe_ack(event.redis_message_id)
            return

        try:
            await self.process_event(event)
            self._mark_processed(event.event_id)
            self.stats_processed += 1
        except Exception:
            self.stats_errors += 1
            logger.exception(
                "reactor.event.error | event_id=%s type=%s",
                event.event_id, event.event_type,
            )
            return

        if event.redis_message_id:
            await self._safe_ack(event.redis_message_id)
        else:
            logger.warning(
                "reactor.ack.skip | event_id=%s — no redis_message_id",
                event.event_id,
            )

    async def _safe_ack(self, message_id: str) -> None:
        """ACK a message, logging but not raising on failure."""
        try:
            await self._bus.ack(STREAM_SENSOR_INGEST, CONSUMER_GROUP, message_id)
        except Exception:
            logger.exception(
                "reactor.ack.error | msg_id=%s — will be redelivered",
                message_id,
            )

    def _is_duplicate(self, event_id: str) -> bool:
        entry = self._processed_ids.get(event_id)
        if entry is None:
            return False
        if (time.monotonic() - entry) > _DEDUP_TTL_SECONDS:
            del self._processed_ids[event_id]
            return False
        return True

    def _mark_processed(self, event_id: str) -> None:
        self._processed_ids[event_id] = time.monotonic()
        while len(self._processed_ids) > _DEDUP_MAX_SIZE:
            self._processed_ids.popitem(last=False)

    async def process_event(self, event: Event) -> None:
        """Route *event* based on its type.

        - ``ingest``  → publish to ``cortex:anomaly`` (placeholder for FactAnalyzer).
        - ``anomaly`` → evaluate risk class and route to the appropriate stream.
        """
        ts = datetime.now(tz=UTC).isoformat()

        if event.event_type == "ingest":
            await self._handle_ingest(event, ts)
        elif event.event_type == "anomaly":
            await self._handle_anomaly(event, ts)
        else:
            logger.warning(
                "reactor.unknown_event_type | ts=%s event_id=%s type=%s",
                ts, event.event_id, event.event_type,
            )

    # ------------------------------------------------------------------
    # Ingest handling
    # ------------------------------------------------------------------

    async def _handle_ingest(self, event: Event, ts: str) -> None:
        """Forward ingest events to ``cortex:anomaly`` for analysis."""
        anomaly_event = Event(
            event_id=f"{event.event_id}-anomaly",
            event_type="anomaly",
            correlation_id=event.correlation_id,
            payload=event.payload,
            risk_class=event.risk_class,
            timestamp=ts,
            source=f"reactor/{CONSUMER_NAME}",
        )
        await self._bus.publish(STREAM_CORTEX_ANOMALY, anomaly_event)
        logger.info(
            "reactor.ingest.forwarded | ts=%s event_id=%s corr=%s → %s",
            ts, event.event_id, event.correlation_id, STREAM_CORTEX_ANOMALY,
        )

    # ------------------------------------------------------------------
    # Anomaly handling — risk-class routing
    # ------------------------------------------------------------------

    async def _handle_anomaly(self, event: Event, ts: str) -> None:
        """Evaluate the anomaly's risk class and route accordingly."""
        risk_class = self._resolve_risk_class(event)

        if risk_class is None:
            logger.error(
                "reactor.anomaly.unknown_risk | ts=%s event_id=%s raw=%s "
                "— routing to consciousness:alert as safety fallback",
                ts, event.event_id, event.risk_class,
            )
            await self._route_rc4_block_alert(event, ts)
            return

        if risk_class == RiskClass.RC1_READ_ONLY:
            await self._route_rc1_auto_execute(event, ts)
        elif risk_class in (
            RiskClass.RC2_AGENT_DRAFT_HUMAN_APPROVE,
            RiskClass.RC3_SUPERVISED_WRITE,
        ):
            await self._route_hitl(event, risk_class, ts)
        elif risk_class == RiskClass.RC4_BULK_STRUCTURAL:
            await self._route_rc4_block_alert(event, ts)

    def _resolve_risk_class(self, event: Event) -> RiskClass | None:
        """Attempt to parse the event's ``risk_class`` field into a ``RiskClass``."""
        raw = event.risk_class
        if raw is None:
            return None
        for rc in RiskClass:
            if raw == rc.value or raw == rc.name or raw == rc:
                return rc
        return None

    async def _route_rc1_auto_execute(self, event: Event, ts: str) -> None:
        """RC-1: auto-execute — log and publish to ``motor:action``."""
        action_event = Event(
            event_id=f"{event.event_id}-action",
            event_type="action",
            correlation_id=event.correlation_id,
            payload={
                **event.payload,
                "risk_class": RiskClass.RC1_READ_ONLY.value,
                "decision": "auto_execute",
                "decided_at": ts,
            },
            risk_class=RiskClass.RC1_READ_ONLY.value,
            timestamp=ts,
            source=f"reactor/{CONSUMER_NAME}",
        )
        await self._bus.publish(STREAM_MOTOR_ACTION, action_event)
        logger.info(
            "reactor.rc1.auto_execute | ts=%s event_id=%s corr=%s → %s",
            ts, event.event_id, event.correlation_id, STREAM_MOTOR_ACTION,
        )

    async def _route_hitl(self, event: Event, risk_class: RiskClass, ts: str) -> None:
        """RC-2 / RC-3: submit to human-in-the-loop approval."""
        approval_required = _RISK_CLASS_APPROVAL_MAP[risk_class]
        hitl_event = Event(
            event_id=f"{event.event_id}-hitl",
            event_type="hitl_request",
            correlation_id=event.correlation_id,
            payload={
                **event.payload,
                "risk_class": risk_class.value,
                "decision": "hitl_submit",
                "approval_required": approval_required,
                "decided_at": ts,
            },
            risk_class=risk_class.value,
            timestamp=ts,
            source=f"reactor/{CONSUMER_NAME}",
        )
        await self._bus.publish(STREAM_IMMUNE_HITL, hitl_event)
        logger.info(
            "reactor.%s.hitl_submit | ts=%s event_id=%s corr=%s approvals=%d → %s",
            risk_class.value, ts, event.event_id, event.correlation_id,
            approval_required, STREAM_IMMUNE_HITL,
        )

    async def _route_rc4_block_alert(self, event: Event, ts: str) -> None:
        """RC-4: block and alert — publish to ``consciousness:alert``."""
        alert_event = Event(
            event_id=f"{event.event_id}-alert",
            event_type="alert",
            correlation_id=event.correlation_id,
            payload={
                **event.payload,
                "risk_class": RiskClass.RC4_BULK_STRUCTURAL.value,
                "decision": "block_and_alert",
                "decided_at": ts,
            },
            risk_class=RiskClass.RC4_BULK_STRUCTURAL.value,
            timestamp=ts,
            source=f"reactor/{CONSUMER_NAME}",
        )
        await self._bus.publish(STREAM_CONSCIOUSNESS_ALERT, alert_event)
        logger.warning(
            "reactor.rc4.block_alert | ts=%s event_id=%s corr=%s → %s",
            ts, event.event_id, event.correlation_id, STREAM_CONSCIOUSNESS_ALERT,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _sleep_or_shutdown(self, seconds: float) -> None:
        """Sleep for *seconds* unless shutdown is requested sooner."""
        try:
            await asyncio.wait_for(self._shutdown.wait(), timeout=seconds)
        except asyncio.TimeoutError:
            pass
