"""Agent daemon — single-threaded asyncio event loop with tiered scheduling."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import shlex
import subprocess
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


def _str_obj_dict() -> dict[str, object]:
    return {}


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

    # Runtime state — excluded from __init__ (internal, not part of the public API)
    _buffer: list[PendingSnapshot] = field(init=False, default_factory=_snapshot_buffer)
    _last_hashes: dict[str, str] = field(init=False, default_factory=_str_str_dict)
    _last_run: dict[str, float] = field(init=False, default_factory=_str_float_dict)
    _schedule: dict[str, int] = field(init=False, default_factory=_str_int_dict)
    _enabled_collectors: list[str] = field(init=False, default_factory=_str_list)
    _running: bool = field(init=False, default=False)
    # Latest heartbeat vitals — kept fresh by the collection loop
    _latest_heartbeat: dict[str, object] = field(init=False, default_factory=_str_obj_dict)

    max_buffer_size: int = 1000
    flush_interval: float = 5.0
    flush_batch_size: int = 10
    redis_url: str = ""

    # Command channel configuration
    _COMMAND_ALLOWLIST: dict[str, list[str]] = field(init=False, default_factory=lambda: {
        "run_diagnostic": [
            "df -h", "ps aux --sort=-%mem | head -20",
            "systemctl list-units --state=failed",
            "systemctl status ", "systemctl restart ",
            "docker ps -a --format json",
            "journalctl -p err --since '1 hour ago' --no-pager | tail -100",
            "uptime", "free -h", "ss -tlnp",
            "openssl x509 -in ",
            "curl -s -o /dev/null -w ",
        ],
        "read_file": [
            "/etc/ssh/sshd_config", "/etc/systemd/",
            "/etc/haproxy/", "/etc/nginx/", "/etc/fail2ban/",
        ],
        "service_status": [],
        "docker_inspect": [],
    })
    _MAX_COMMAND_OUTPUT: int = field(init=False, default=65_536)

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

        tasks = [
            self._collection_loop(),
            self._flush_loop(),
            self._heartbeat_ping_loop(),
        ]
        if self.redis_url:
            tasks.append(self._command_listener_loop())
        await asyncio.gather(*tasks)

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

    # ------------------------------------------------------------------
    # Command Channel — Redis pub/sub listener
    # ------------------------------------------------------------------

    async def _command_listener_loop(self) -> None:
        """Listen for commands on the agent's Redis channel."""
        try:
            import redis.asyncio as aioredis  # noqa: PLC0415
        except ImportError:
            logger.warning("redis package not available — command channel disabled")
            return

        channel_name = f"infraq:agent:{self.agent_id}:commands"
        logger.info("Command channel listening on %s", channel_name)

        while self._running:
            try:
                r = aioredis.from_url(self.redis_url, decode_responses=True)
                try:
                    pubsub = r.pubsub()
                    await pubsub.subscribe(channel_name)
                    while self._running:
                        message = await pubsub.get_message(
                            ignore_subscribe_messages=True, timeout=1.0,
                        )
                        if message is None:
                            continue
                        if message["type"] != "message":
                            continue
                        await self._handle_command(message["data"])
                    await pubsub.unsubscribe(channel_name)
                finally:
                    await r.aclose()
            except Exception:
                logger.exception("Command listener error — reconnecting in 5s")
                await asyncio.sleep(5)

    async def _handle_command(self, raw_message: str) -> None:
        """Parse, validate, and execute a received command."""
        try:
            cmd = json.loads(raw_message)
        except (json.JSONDecodeError, TypeError):
            logger.warning("Invalid command JSON received")
            return

        command_id = cmd.get("command_id", "")
        command_type = cmd.get("command_type", "")
        payload = cmd.get("payload", {})
        timeout = min(cmd.get("timeout", 30), 120)
        signature = cmd.get("signature", "")

        # Verify HMAC signature — mandatory for all commands
        if not self.api_token:
            logger.warning("Command %s: no api_token configured, rejecting", command_id)
            await self._send_command_result(command_id, {
                "error": "Agent has no API token configured",
                "exit_code": -1,
            })
            return

        if not signature:
            logger.warning("Command %s: missing HMAC signature, rejecting", command_id)
            await self._send_command_result(command_id, {
                "error": "HMAC signature required",
                "exit_code": -1,
            })
            return

        payload_json = json.dumps(payload, sort_keys=True)
        expected = hmac.new(
            self.api_token.encode(),
            f"{command_id}:{payload_json}".encode(),
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(signature, expected):
            logger.warning("Command %s: HMAC verification failed", command_id)
            await self._send_command_result(command_id, {
                "error": "HMAC verification failed",
                "exit_code": -1,
            })
            return

        # Execute command
        logger.info("Executing command %s: %s", command_id, command_type)
        t0 = time.monotonic()
        try:
            payload["_subprocess_timeout"] = timeout
            async with asyncio.timeout(timeout + 5):
                result = await self._execute_command(command_type, payload)
            duration_ms = int((time.monotonic() - t0) * 1000)
            result["duration_ms"] = duration_ms
        except TimeoutError:
            duration_ms = int((time.monotonic() - t0) * 1000)
            result = {
                "error": "Command timed out",
                "exit_code": -1,
                "duration_ms": duration_ms,
            }
        except Exception as exc:
            duration_ms = int((time.monotonic() - t0) * 1000)
            result = {
                "error": str(exc),
                "exit_code": -1,
                "duration_ms": duration_ms,
            }
            logger.exception("Command %s failed", command_id)

        await self._send_command_result(command_id, result)

    async def _execute_command(
        self, command_type: str, payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Dispatch and execute a command by type."""
        if command_type == "run_diagnostic":
            return await self._cmd_run_diagnostic(payload)
        if command_type == "read_file":
            return await self._cmd_read_file(payload)
        if command_type == "service_status":
            return await self._cmd_service_status(payload)
        if command_type == "docker_inspect":
            return await self._cmd_docker_inspect(payload)
        return {"error": f"Unknown command_type: {command_type}", "exit_code": -1}

    async def _cmd_run_diagnostic(
        self, payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute a read-only diagnostic shell command."""
        shell_cmd = payload.get("command", "")
        allowed = self._COMMAND_ALLOWLIST.get("run_diagnostic", [])
        if not any(shell_cmd.startswith(a) for a in allowed):
            return {"error": f"Command not in allowlist: {shell_cmd}", "exit_code": -1}

        subprocess_timeout = payload.get("_subprocess_timeout", 30)
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self._run_subprocess, shell_cmd, subprocess_timeout,
        )

    @staticmethod
    def _run_subprocess(cmd: str, timeout: int) -> dict[str, Any]:
        """Run a subprocess safely with output truncation."""
        try:
            result = subprocess.run(  # noqa: S603
                shlex.split(cmd),
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            stdout = result.stdout[:65_536]
            stderr = result.stderr[:65_536]
            return {
                "stdout": stdout,
                "stderr": stderr,
                "exit_code": result.returncode,
            }
        except subprocess.TimeoutExpired:
            return {"error": "Subprocess timed out", "exit_code": -1, "stdout": "", "stderr": ""}
        except FileNotFoundError:
            return {"error": f"Command not found: {cmd}", "exit_code": -1}

    async def _cmd_read_file(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Read a configuration file (allowlisted paths only)."""
        file_path = payload.get("path", "")
        allowed_prefixes = self._COMMAND_ALLOWLIST.get("read_file", [])
        if not any(file_path.startswith(p) for p in allowed_prefixes):
            return {"error": f"Path not in allowlist: {file_path}", "exit_code": -1}
        if ".." in file_path:
            return {"error": "Path traversal blocked", "exit_code": -1}

        import pathlib  # noqa: PLC0415



        loop = asyncio.get_event_loop()

        def _read() -> dict[str, Any]:
            p = pathlib.Path(file_path)
            if not p.exists():
                return {"error": f"File not found: {file_path}", "exit_code": 1}
            if not p.is_file():
                return {"error": f"Not a file: {file_path}", "exit_code": 1}
            content = p.read_text(errors="replace")[:65_536]
            return {"stdout": content, "stderr": "", "exit_code": 0}

        return await loop.run_in_executor(None, _read)

    async def _cmd_service_status(
        self, payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Get systemd service status."""
        service = payload.get("service", "")
        if not service or "/" in service or ".." in service:
            return {"error": f"Invalid service name: {service}", "exit_code": -1}
        cmd = f"systemctl status {service} --no-pager"
        return await self._cmd_run_diagnostic({
            "command": cmd,
            "_subprocess_timeout": payload.get("_subprocess_timeout", 30),
        })

    async def _cmd_docker_inspect(
        self, payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Inspect a Docker container."""
        container = payload.get("container", "")
        if not container or "/" in container or ".." in container:
            return {"error": f"Invalid container name: {container}", "exit_code": -1}
        cmd = f"docker inspect {container}"
        subprocess_timeout = payload.get("_subprocess_timeout", 30)
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self._run_subprocess, cmd, subprocess_timeout,
        )

    async def _send_command_result(
        self, command_id: str, result: dict[str, Any],
    ) -> None:
        """Publish command result back to Redis and update API."""
        # Publish to Redis results channel
        try:
            import redis.asyncio as aioredis  # noqa: PLC0415

            r = aioredis.from_url(self.redis_url, decode_responses=True)
            try:
                channel = f"infraq:agent:results:{command_id}"
                await r.publish(channel, json.dumps(result))
            finally:
                await r.aclose()
        except Exception:
            logger.debug("Redis result publish failed for %s", command_id)

        # Also report back to API
        if self.agent_id:
            url = f"{self.api_url}/agent-commands/{self.agent_id}/commands/{command_id}/result"
            headers = self._auth_headers()
            try:
                async with httpx.AsyncClient(timeout=10, verify=self._ssl_verify) as client:
                    await client.post(url, json=result, headers=headers)
            except httpx.HTTPError:
                logger.debug("Result POST failed for command %s", command_id)
