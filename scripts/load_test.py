"""Load test for internalCMDB API — simulates 17 agents at 15s intervals.

Run with (staging):
    locust -f scripts/load_test.py --host http://localhost:4444 --headless \
        -u 17 --spawn-rate 1 -t 5m --csv results/load_test

Safety: the script refuses to run against production (infraq.app) unless
LOAD_TEST_ALLOW_PROD=1 is set explicitly.

Targets: p99 < 500ms for all endpoints.
"""

from __future__ import annotations

import os
import random
import sys
import uuid

from locust import HttpUser, between, events, task


@events.test_start.add_listener
def _check_target_host(environment: object, **_kwargs: object) -> None:
    """Abort immediately if targeting production without explicit opt-in."""
    host = getattr(environment, "host", "") or ""
    if "infraq.app" in host and os.environ.get("LOAD_TEST_ALLOW_PROD") != "1":
        print(  # noqa: T201
            "ERROR: refusing to load-test production (infraq.app). "
            "Set LOAD_TEST_ALLOW_PROD=1 to override.",
            file=sys.stderr,
        )
        sys.exit(1)


class AgentUser(HttpUser):
    """Simulates a collector agent sending telemetry."""

    wait_time = between(12, 18)

    def on_start(self) -> None:
        self.agent_id = str(uuid.uuid4())
        self.host_code = f"load-test-{random.randint(1, 999):03d}"
        self.api_token = ""
        self._enroll()

    def _enroll(self) -> None:
        resp = self.client.post(
            "/api/v1/collectors/enroll",
            json={
                "host_code": self.host_code,
                "agent_version": "1.0.0-loadtest",
                "capabilities": ["heartbeat", "system_vitals", "docker_state"],
            },
            name="/collectors/enroll",
        )
        if resp.status_code == 201:
            data = resp.json()
            self.agent_id = data["agent_id"]
            self.api_token = data.get("api_token", "")

    def _auth_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_token}",
            "X-Agent-ID": str(self.agent_id),
        }

    @task(10)
    def ingest_snapshot(self) -> None:
        self.client.post(
            "/api/v1/collectors/ingest",
            json={
                "agent_id": self.agent_id,
                "snapshots": [
                    {
                        "snapshot_kind": "system_vitals",
                        "tier_code": "15s",
                        "payload": {
                            "cpu_pct": random.uniform(5, 95),
                            "memory_pct": random.uniform(20, 85),
                            "load_avg": [random.uniform(0, 4) for _ in range(3)],
                        },
                        "collected_at": "2025-01-01T00:00:00Z",
                        "payload_hash": uuid.uuid4().hex,
                    }
                ],
            },
            headers=self._auth_headers(),
            name="/collectors/ingest",
        )

    @task(3)
    def cognitive_query(self) -> None:
        self.client.post(
            "/api/v1/cognitive/query",
            json={
                "question": "What is the current CPU usage across the fleet?",
                "top_k": 8,
            },
            headers=self._auth_headers(),
            name="/cognitive/query",
        )

    @task(1)
    def hitl_queue(self) -> None:
        self.client.get(
            "/api/v1/hitl/queue",
            headers=self._auth_headers(),
            name="/hitl/queue",
        )

    @task(2)
    def fleet_matrix(self) -> None:
        self.client.get(
            "/api/v1/metrics/fleet/matrix",
            headers=self._auth_headers(),
            name="/metrics/fleet/matrix",
        )

    @task(5)
    def heartbeat(self) -> None:
        self.client.post(
            "/api/v1/collectors/heartbeat",
            json={
                "agent_id": self.agent_id,
                "agent_version": "1.0.0-loadtest",
                "uptime_seconds": random.uniform(1000, 500000),
                "load_avg": [random.uniform(0, 4) for _ in range(3)],
                "memory_pct": random.uniform(20, 85),
            },
            headers=self._auth_headers(),
            name="/collectors/heartbeat",
        )
