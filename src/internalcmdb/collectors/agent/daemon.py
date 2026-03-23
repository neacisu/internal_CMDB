"""Agent daemon — single-threaded asyncio event loop with tiered scheduling."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import httpx

from internalcmdb.collectors.schedule_tiers import TIERS

from .collectors import (
    certificate_state,
    container_resources,
    disk_state,
    docker_state,
    full_audit,
    full_hardware,
    gpu_state,
    heartbeat,
    journal_errors,
    llm_endpoint_health,
    network_latency,
    network_state,
    process_inventory,
    security_posture,
    service_health,
    system_vitals,
    systemd_state,
    trust_surface_lite,
    vllm_metrics,
)

logger = logging.getLogger("internalcmdb.agent")

# Collector name → module mapping
COLLECTOR_MODULES: dict[str, Any] = {
    "heartbeat": heartbeat,
    "system_vitals": system_vitals,
    "docker_state": docker_state,
    "container_resources": container_resources,
    "gpu_state": gpu_state,
    "vllm_metrics": vllm_metrics,
    "llm_endpoint_health": llm_endpoint_health,
    "service_health": service_health,
    "network_state": network_state,
    "network_latency": network_latency,
    "disk_state": disk_state,
    "process_inventory": process_inventory,
    "systemd_state": systemd_state,
    "journal_errors": journal_errors,
    "trust_surface_lite": trust_surface_lite,
    "certificate_state": certificate_state,
    "security_posture": security_posture,
    "full_hardware": full_hardware,
    "full_audit": full_audit,
}

# Collector → tier mapping (reverse lookup)
COLLECTOR_TO_TIER: dict[str, str] = {}
for _code, _tier in TIERS.items():
    for _coll in _tier.collectors:
        COLLECTOR_TO_TIER[_coll] = _code


@dataclass
class PendingSnapshot:
    """A snapshot waiting to be sent."""

    snapshot_kind: str
    tier_code: str
    payload: dict[str, Any]
    payload_hash: str
    collected_at: str


def _snapshot_buffer() -> list[PendingSnapshot]:
    return []


def _str_str_dict() -> dict[str, str]:
    return {}


def _str_float_dict() -> dict[str, float]:
    return {}


def _str_int_dict() -> dict[str, int]:
    return {}


def _str_list() -> list[str]:
    return []


@dataclass
class AgentDaemon:
    """Main agent daemon — collects and pushes telemetry."""

    api_url: str
    host_code: str
    agent_id: str | None = None
    api_token: str | None = None
    agent_version: str = "1.0.0"
    enrollment_token: str = ""
    log_level: str = "INFO"
    verify_ssl: bool = True
    ca_bundle: str | None = None

    # Runtime state
    _buffer: list[PendingSnapshot] = field(default_factory=_snapshot_buffer)
    _last_hashes: dict[str, str] = field(default_factory=_str_str_dict)
    _last_run: dict[str, float] = field(default_factory=_str_float_dict)
    _schedule: dict[str, int] = field(default_factory=_str_int_dict)
    _enabled_collectors: list[str] = field(default_factory=_str_list)
    _running: bool = False
    # Latest heartbeat vitals — kept fresh by the collection loop
    _latest_heartbeat: dict[str, object] = field(default_factory=dict)

    max_buffer_size: int = 1000
    flush_interval: float = 5.0
    flush_batch_size: int = 10

    @property
    def _ssl_verify(self) -> bool | str:
        """Return the ssl verify param: CA bundle path if set, else bool."""
        if self.ca_bundle and self.verify_ssl:
            return self.ca_bundle
        return self.verify_ssl

    def _auth_headers(self) -> dict[str, str]:
        """Build Authorization and X-Agent-ID headers for authenticated requests."""
        if not self.agent_id or not self.api_token:
            return {}
        return {
            "Authorization": f"Bearer {self.api_token}",
            "X-Agent-ID": str(self.agent_id),
        }

    async def start(self) -> None:
        """Enroll with the API and start the collection loop."""
        logging.basicConfig(level=getattr(logging, self.log_level))
        logger.info("Agent starting for host %s", self.host_code)

        await self._enroll()
        self._running = True

        await asyncio.gather(
            self._collection_loop(),
            self._flush_loop(),
            self._heartbeat_ping_loop(),
        )

    async def _enroll(self) -> None:
        """Register with the control plane."""
        url = f"{self.api_url}/enroll"
        capabilities = list(COLLECTOR_MODULES.keys())

        async with httpx.AsyncClient(timeout=30, verify=self._ssl_verify) as client:
            resp = await client.post(
                url,
                json={
                    "host_code": self.host_code,
                    "agent_version": self.agent_version,
                    "capabilities": capabilities,
                },
            )
            resp.raise_for_status()
            data = resp.json()

        self.agent_id = data["agent_id"]
        self.api_token = data["api_token"]
        self._schedule = data.get("schedule_tiers", {})
        self._enabled_collectors = data.get("enabled_collectors", capabilities)

        logger.info("Enrolled as agent %s", self.agent_id)

    async def _collection_loop(self) -> None:
        """Run collectors at their configured intervals."""
        while self._running:
            now = time.monotonic()

            for collector_name in self._enabled_collectors:
                tier_code = COLLECTOR_TO_TIER.get(collector_name)
                if tier_code is None:
                    continue

                interval = self._schedule.get(tier_code, TIERS[tier_code].interval_seconds)
                last = self._last_run.get(collector_name, 0.0)

                if now - last < interval:
                    continue

                self._last_run[collector_name] = now
                await self._run_collector(collector_name, tier_code)

            await asyncio.sleep(1)

    async def _run_collector(self, name: str, tier_code: str) -> None:
        """Execute a collector and buffer the result."""
        module = COLLECTOR_MODULES.get(name)
        if module is None:
            return

        try:
            loop = asyncio.get_event_loop()
            payload = await loop.run_in_executor(None, module.collect)
        except Exception:
            logger.exception("Collector %s failed", name)
            return

        # Compute hash for dedup
        payload_bytes = json.dumps(payload, sort_keys=True).encode()
        payload_hash = hashlib.sha256(payload_bytes).hexdigest()

        # Local dedup — skip if unchanged
        if self._last_hashes.get(name) == payload_hash:
            return
        self._last_hashes[name] = payload_hash

        snapshot = PendingSnapshot(
            snapshot_kind=name,
            tier_code=tier_code,
            payload=payload,
            payload_hash=payload_hash,
            collected_at=datetime.now(UTC).isoformat(),
        )

        # Cache latest heartbeat vitals for the dedicated ping loop
        if name == "heartbeat":
            self._latest_heartbeat = payload

        if len(self._buffer) < self.max_buffer_size:
            self._buffer.append(snapshot)
        else:
            logger.warning("Buffer full (%d items), dropping snapshot", self.max_buffer_size)

    async def _flush_loop(self) -> None:
        """Periodically flush buffered snapshots to the API."""
        while self._running:
            await asyncio.sleep(self.flush_interval)
            await self._flush()

    async def _flush(self) -> None:
        """Send buffered snapshots to the ingest endpoint."""
        if not self._buffer or not self.agent_id:
            return

        batch = self._buffer[: self.flush_batch_size]
        self._buffer = self._buffer[self.flush_batch_size :]

        url = f"{self.api_url}/ingest"
        payload = {
            "agent_id": self.agent_id,
            "snapshots": [
                {
                    "snapshot_kind": s.snapshot_kind,
                    "tier_code": s.tier_code,
                    "payload": s.payload,
                    "collected_at": s.collected_at,
                    "payload_hash": s.payload_hash,
                }
                for s in batch
            ],
        }

        headers = self._auth_headers()
        try:
            async with httpx.AsyncClient(timeout=30, verify=self._ssl_verify) as client:
                resp = await client.post(url, json=payload, headers=headers)
                if resp.status_code == 200:  # noqa: PLR2004
                    data = resp.json()
                    logger.debug(
                        "Flushed %d accepted, %d deduped",
                        data.get("accepted", 0),
                        data.get("deduplicated", 0),
                    )
                else:
                    logger.warning(
                        "Ingest returned %d, re-buffering %d items",
                        resp.status_code,
                        len(batch),
                    )
                    self._buffer = batch + self._buffer
        except httpx.HTTPError:
            logger.warning("API unreachable, re-buffering %d items", len(batch))
            self._buffer = batch + self._buffer

    async def _heartbeat_ping_loop(self) -> None:
        """Send a lightweight POST /heartbeat every flush_interval seconds.

        This runs independently of the snapshot buffer so the control plane
        always sees a fresh ``last_heartbeat_at`` even when every snapshot is
        deduplicated and the ingest buffer stays empty.
        """
        while self._running:
            await asyncio.sleep(self.flush_interval)
            if not self.agent_id:
                continue
            vitals = self._latest_heartbeat
            url = f"{self.api_url}/heartbeat"
            body = {
                "agent_id": self.agent_id,
                "agent_version": self.agent_version,
                "uptime_seconds": vitals.get("uptime_seconds", 0.0),
                "load_avg": vitals.get("load_avg", []),
                "memory_pct": vitals.get("memory_pct"),
            }
            headers = self._auth_headers()
            try:
                async with httpx.AsyncClient(timeout=10, verify=self._ssl_verify) as client:
                    resp = await client.post(url, json=body, headers=headers)
                    if resp.status_code != 200:  # noqa: PLR2004
                        logger.debug("Heartbeat ping returned %d", resp.status_code)
            except httpx.HTTPError:
                logger.debug("Heartbeat ping failed — API unreachable")

    async def stop(self) -> None:
        """Gracefully stop the daemon."""
        self._running = False
        await self._flush()
        logger.info("Agent stopped")
