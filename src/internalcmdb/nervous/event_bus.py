"""EventBus — Redis Streams backbone for the nervous-system event fabric."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, ClassVar
from uuid import uuid4

import redis.asyncio as aioredis
from redis.exceptions import RedisError

logger = logging.getLogger(__name__)

_MAX_STREAM_LEN = 50_000
_MAX_PAYLOAD_BYTES = 512 * 1024  # 512 KiB


@dataclass
class Event:
    """Canonical event envelope carried on every stream."""

    event_id: str = ""
    event_type: str = ""
    correlation_id: str = ""
    timestamp: str = ""
    source: str = ""
    payload: dict[str, Any] = field(default_factory=dict)  # pyright: ignore[reportUnknownVariableType]
    risk_class: str = "RC-1"
    redis_message_id: str = field(default="", init=False, repr=False)

    def __post_init__(self) -> None:
        if not self.event_id:
            self.event_id = str(uuid4())
        if not self.timestamp:
            self.timestamp = datetime.now(tz=UTC).isoformat()
        if not self.correlation_id:
            self.correlation_id = str(uuid4())

    def to_dict(self) -> dict[str, str]:
        """Serialize to a flat string dict suitable for ``XADD``.

        Raises ``ValueError`` when the payload cannot be serialised or
        exceeds ``_MAX_PAYLOAD_BYTES``.
        """
        try:
            payload_json = json.dumps(self.payload, default=str)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Event {self.event_id}: payload serialisation failed: {exc}") from exc

        if len(payload_json.encode()) > _MAX_PAYLOAD_BYTES:
            raise ValueError(
                f"Event {self.event_id}: payload size "
                f"{len(payload_json.encode())} bytes exceeds "
                f"limit of {_MAX_PAYLOAD_BYTES} bytes"
            )

        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "correlation_id": self.correlation_id,
            "timestamp": self.timestamp,
            "source": self.source,
            "payload": payload_json,
            "risk_class": self.risk_class,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Event:
        """Reconstruct an *Event* from the dict returned by ``XREADGROUP``."""
        payload_raw = data.get("payload", "{}")
        if isinstance(payload_raw, str):
            try:
                payload = json.loads(payload_raw)
            except json.JSONDecodeError, TypeError:
                payload = {}
        elif isinstance(payload_raw, dict):
            payload: dict[str, Any] = payload_raw  # pyright: ignore[reportUnknownVariableType]
        else:
            payload = {}

        return cls(
            event_id=str(data.get("event_id", "")),
            event_type=str(data.get("event_type", "")),
            correlation_id=str(data.get("correlation_id", "")),
            timestamp=str(data.get("timestamp", "")),
            source=str(data.get("source", "")),
            payload=payload,
            risk_class=str(data.get("risk_class", "RC-1")),
        )


class EventBus:
    """Async publish / subscribe broker over Redis Streams."""

    STREAMS: ClassVar[dict[str, str]] = {
        "sensor:ingest": "sensor:ingest",
        "sensor:metric": "sensor:metric",
        "cortex:anomaly": "cortex:anomaly",
        "cortex:drift": "cortex:drift",
        "cortex:insight": "cortex:insight",
        "motor:action": "motor:action",
        "immune:gate": "immune:gate",
        "immune:hitl": "immune:hitl",
        "memory:feedback": "memory:feedback",
        "consciousness:alert": "consciousness:alert",
    }

    def __init__(self, redis_url: str) -> None:
        self._redis: aioredis.Redis = aioredis.from_url(  # type: ignore[no-untyped-call,assignment]
            redis_url,
            decode_responses=True,
        )

    async def __aenter__(self) -> EventBus:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()

    # ------------------------------------------------------------------
    # Publish
    # ------------------------------------------------------------------

    async def publish(
        self,
        stream: str,
        event: Event,
        maxlen: int = _MAX_STREAM_LEN,
    ) -> str:
        """``XADD`` *event* to *stream* and return the Redis message ID.

        Caps the stream at *maxlen* entries (approximate trimming) to
        prevent unbounded memory growth.
        """
        try:
            fields: Any = event.to_dict()
            message_id: str = await self._redis.xadd(  # type: ignore[no-untyped-call,assignment]
                stream,
                fields,
                maxlen=maxlen,
                approximate=True,
            )
            logger.info(
                "Published %s to %s (msg_id=%s)",
                event.event_type,
                stream,
                message_id,
            )
            return message_id
        except RedisError:
            logger.exception(
                "Failed to publish event %s to stream %s",
                event.event_id,
                stream,
            )
            raise

    # ------------------------------------------------------------------
    # Subscribe
    # ------------------------------------------------------------------

    async def subscribe(
        self,
        stream: str,
        group: str,
        consumer: str,
        count: int = 10,
        block_ms: int = 5000,
    ) -> list[Event]:
        """``XREADGROUP`` and return decoded events.

        Creates the consumer group automatically when it does not exist.
        Each returned :class:`Event` carries its Redis message ID in
        ``event.redis_message_id`` so callers can :meth:`ack` it.
        """
        try:
            await self._ensure_group(stream, group)
            resp = await self._redis.xreadgroup(
                groupname=group,
                consumername=consumer,
                streams={stream: ">"},
                count=count,
                block=block_ms,
            )
        except RedisError:
            logger.exception(
                "Failed to subscribe to %s (group=%s)",
                stream,
                group,
            )
            raise

        events: list[Event] = []
        if resp:
            for _stream_name, messages in resp:
                for msg_id, fields in messages:
                    event = Event.from_dict(fields)
                    event.redis_message_id = str(msg_id)
                    events.append(event)
                    logger.debug(
                        "Received %s from %s (msg_id=%s)",
                        event.event_type,
                        stream,
                        msg_id,
                    )
        return events

    # ------------------------------------------------------------------
    # Acknowledge
    # ------------------------------------------------------------------

    async def ack(self, stream: str, group: str, message_id: str) -> None:
        """``XACK`` a single message."""
        try:
            await self._redis.xack(stream, group, message_id)
            logger.debug(
                "ACK %s on %s (group=%s)",
                message_id,
                stream,
                group,
            )
        except RedisError:
            logger.exception(
                "Failed to ACK %s on %s",
                message_id,
                stream,
            )
            raise

    # ------------------------------------------------------------------
    # Consumer-group management
    # ------------------------------------------------------------------

    async def ensure_groups(self) -> None:
        """Pre-create a default consumer group for every registered stream."""
        for stream in self.STREAMS:
            await self._ensure_group(stream, f"{stream}:default")

    async def _ensure_group(self, stream: str, group: str) -> None:
        try:
            await self._redis.xgroup_create(
                name=stream,
                groupname=group,
                id="0",
                mkstream=True,
            )
            logger.info(
                "Created consumer group %s on stream %s",
                group,
                stream,
            )
        except RedisError as exc:
            if "BUSYGROUP" in str(exc):
                return
            logger.exception(
                "Failed to create consumer group %s on %s",
                group,
                stream,
            )
            raise

    # ------------------------------------------------------------------
    # Health & pending-message recovery
    # ------------------------------------------------------------------

    async def ping(self) -> bool:
        """Return ``True`` if the Redis backend responds to PING."""
        try:
            return bool(await self._redis.ping())  # pyright: ignore[reportUnknownMemberType]
        except RedisError:
            return False

    async def claim_stale_messages(
        self,
        stream: str,
        group: str,
        consumer: str,
        min_idle_ms: int = 60_000,
        count: int = 50,
    ) -> list[Event]:
        """Claim pending messages idle longer than *min_idle_ms* (XAUTOCLAIM).

        Prevents messages from being stuck in a dead consumer's PEL.
        Returns the claimed events (caller must ACK after processing).
        """
        try:
            _, messages, _ = await self._redis.xautoclaim(  # type: ignore[misc]
                name=stream,
                groupname=group,
                consumername=consumer,
                min_idle_time=min_idle_ms,
                count=count,
            )
        except RedisError:
            logger.exception(
                "Failed to XAUTOCLAIM on %s (group=%s)",
                stream,
                group,
            )
            return []

        events: list[Event] = []
        for msg_id, fields in messages:
            if fields is None:
                continue
            event = Event.from_dict(fields)
            event.redis_message_id = str(msg_id)
            events.append(event)
        return events

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def close(self) -> None:
        """Gracefully close the underlying Redis connection."""
        await self._redis.aclose()
