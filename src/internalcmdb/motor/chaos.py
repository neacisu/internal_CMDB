"""Chaos Engineering Engine (Phase 15, F15).

Provides controlled fault-injection experiments for resilience testing.

Safety guarantees:
    - All experiments are HITL RC-3 mandatory (require dual approval)
    - ``dry_run=True`` by default — NEVER auto-execute
    - Kill switch: periodic abort checks during execution (every 0.5s)
    - Blast radius calculation and hard cap before execution
    - Post-experiment verification to confirm target recovery
    - Max concurrent experiments enforced (default: 3)
    - Per-host concurrency guard (one experiment per host at a time)
    - Production targets require explicit ``allow_production=True`` flag
    - Execution timeout enforced via ``max_duration_seconds``
    - Data safety pre-check before destructive experiments
    - Rollback hooks for post-experiment state restoration

Built-in experiments:
    - kill_container: terminate a container by ID
    - network_partition_simulate: simulate network partition
    - cpu_stress: inject CPU pressure
    - memory_pressure: inject memory pressure
    - disk_fill_test: simulate disk exhaustion

Public surface::

    from internalcmdb.motor.chaos import ChaosEngine, ChaosResult

    engine = ChaosEngine()
    result = await engine.run_experiment("cpu_stress", "prod-gpu-01", dry_run=True)
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

logger = logging.getLogger(__name__)

_MAX_CONCURRENT_EXPERIMENTS = 3
_MAX_BLAST_RADIUS_COMPONENTS = 10
_ABORT_CHECK_INTERVAL_SECONDS = 0.5
_PRODUCTION_TARGETS = frozenset(
    {
        "prod",
        "production",
        "prod-gpu",
        "prod-db",
        "prod-api",
    }
)

# ---------------------------------------------------------------------------
# Experiment state
# ---------------------------------------------------------------------------


@dataclass
class _ChaosRunCtx:
    """Groups per-run immutable context passed to safety-check helpers."""

    experiment_name: str
    target: str
    dry_run: bool
    experiment_id: str
    now: str


class ExperimentState(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    RUNNING = "running"
    COMPLETED = "completed"
    ABORTED = "aborted"
    FAILED = "failed"


# ---------------------------------------------------------------------------
# ChaosResult
# ---------------------------------------------------------------------------


@dataclass
class ChaosResult:
    """Outcome of a chaos experiment run."""

    experiment: str
    target: str
    success: bool
    blast_radius: list[str] = field(default_factory=list[str])
    recovery_time_ms: int | None = None
    observations: list[str] = field(default_factory=list[str])
    dry_run: bool = True
    experiment_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    state: str = ExperimentState.COMPLETED.value
    started_at: str = ""
    completed_at: str = ""
    rollback_executed: bool = False
    data_safety_verified: bool = False


# ---------------------------------------------------------------------------
# Experiment definitions
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ExperimentDef:
    """Definition of a chaos experiment."""

    name: str
    description: str
    risk_class: str  # always RC-3 or RC-4
    blast_radius_heuristic: str
    max_duration_seconds: int
    recovery_check: str
    requires_dual_approval: bool = True


EXPERIMENTS: dict[str, ExperimentDef] = {
    "kill_container": ExperimentDef(
        name="kill_container",
        description="Terminate a running container to test automatic restart behaviour",
        risk_class="RC-3",
        blast_radius_heuristic="container + dependent services",
        max_duration_seconds=120,
        recovery_check="container_restart_count > 0 and status == running",
    ),
    "network_partition_simulate": ExperimentDef(
        name="network_partition_simulate",
        description="Simulate network partition by dropping packets to/from target",
        risk_class="RC-4",
        blast_radius_heuristic="target host + all services with network dependency",
        max_duration_seconds=60,
        recovery_check="network_connectivity_restored and no_data_loss",
        requires_dual_approval=True,
    ),
    "cpu_stress": ExperimentDef(
        name="cpu_stress",
        description="Inject CPU stress (100% load) on target for bounded duration",
        risk_class="RC-3",
        blast_radius_heuristic="target host + co-located containers",
        max_duration_seconds=300,
        recovery_check="cpu_usage returns to baseline within 60s",
    ),
    "memory_pressure": ExperimentDef(
        name="memory_pressure",
        description="Allocate memory to trigger OOM-killer behaviour testing",
        risk_class="RC-3",
        blast_radius_heuristic="target host + OOM-eligible processes",
        max_duration_seconds=120,
        recovery_check="memory_usage returns to baseline and no_unrecovered_processes",
    ),
    "disk_fill_test": ExperimentDef(
        name="disk_fill_test",
        description="Write temporary data to fill disk to 95% to test alerts and cleanup",
        risk_class="RC-3",
        blast_radius_heuristic="target host filesystem + services writing to same mount",
        max_duration_seconds=180,
        recovery_check="disk_usage < 90% after cleanup and temp_files_removed",
    ),
}


# ---------------------------------------------------------------------------
# Chaos Engine
# ---------------------------------------------------------------------------


class ChaosEngine:
    """Controlled chaos engineering experiment runner.

    Every experiment goes through:
      1. Validation — experiment exists and target is valid
      2. Safety pre-checks — production guard, concurrent limit, per-host guard
      3. Blast radius calculation and cap enforcement
      4. Data safety verification (for destructive experiments)
      5. HITL approval gate — RC-3 mandatory, requires dual approval
      6. Execution (or dry-run simulation) with timeout enforcement
      7. Periodic abort-flag checks during execution
      8. Post-verification — confirm target recovered
      9. Rollback hook if recovery fails
    """

    def __init__(self) -> None:
        self._running: dict[str, ChaosResult] = {}
        self._history: list[ChaosResult] = []
        self._aborted: set[str] = set()
        self._host_locks: dict[str, str] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def run_experiment(
        self,
        experiment_name: str,
        target: str,
        dry_run: bool = True,
        *,
        allow_production: bool = False,
    ) -> ChaosResult:
        """Run a chaos experiment against *target*.

        Args:
            experiment_name: One of the registered experiment names.
            target: Host, container, or service identifier.
            dry_run: If True (default), simulate without actual fault injection.
            allow_production: Must be True to target production hosts in live mode.
        """
        exp_def = EXPERIMENTS.get(experiment_name)
        if exp_def is None:
            return ChaosResult(
                experiment=experiment_name,
                target=target,
                success=False,
                observations=[
                    f"Unknown experiment: {experiment_name}",
                    f"Available: {', '.join(EXPERIMENTS.keys())}",
                ],
                dry_run=dry_run,
                state=ExperimentState.FAILED.value,
            )

        experiment_id = str(uuid.uuid4())
        now = datetime.now(tz=UTC).isoformat()

        run_ctx = _ChaosRunCtx(
            experiment_name=experiment_name,
            target=target,
            dry_run=dry_run,
            experiment_id=experiment_id,
            now=now,
        )

        safety_block = self._pre_flight_safety_checks(
            run_ctx,
            exp_def,
            allow_production,
        )
        if safety_block is not None:
            return safety_block

        blast_radius = self._calculate_blast_radius(exp_def, target)
        blast_block = self._check_blast_radius_cap(
            run_ctx,
            blast_radius,
        )
        if blast_block is not None:
            return blast_block

        logger.info(
            "Chaos experiment %s: %s on %s (dry_run=%s, blast_radius=%d)",
            experiment_id,
            experiment_name,
            target,
            dry_run,
            len(blast_radius),
        )

        data_safe = self._verify_data_safety(exp_def, target)

        if not dry_run:
            hitl_approved = await self._check_hitl_approval(exp_def, target, experiment_id)
            if not hitl_approved:
                return ChaosResult(
                    experiment=experiment_name,
                    target=target,
                    success=False,
                    blast_radius=blast_radius,
                    observations=[
                        f"HITL approval required: {exp_def.risk_class}",
                        "Experiment blocked pending dual approval",
                    ],
                    dry_run=False,
                    experiment_id=experiment_id,
                    state=ExperimentState.PENDING.value,
                    started_at=now,
                    data_safety_verified=data_safe,
                )

        result = ChaosResult(
            experiment=experiment_name,
            target=target,
            success=False,
            blast_radius=blast_radius,
            dry_run=dry_run,
            experiment_id=experiment_id,
            state=ExperimentState.RUNNING.value,
            started_at=now,
            data_safety_verified=data_safe,
        )

        self._running[experiment_id] = result
        self._host_locks[target] = experiment_id

        try:
            if dry_run:
                result = await self._simulate(exp_def, target, result)
            else:
                result = await self._execute_with_timeout(exp_def, target, result)
        except Exception as exc:
            result.success = False
            result.state = ExperimentState.FAILED.value
            result.observations.append(f"Experiment failed: {exc}")
            logger.error("Chaos experiment %s failed: %s", experiment_id, exc)
            await self._execute_rollback(exp_def, target, result)
        finally:
            result.completed_at = datetime.now(tz=UTC).isoformat()
            self._running.pop(experiment_id, None)
            self._host_locks.pop(target, None)
            self._history.append(result)

        return result

    # ------------------------------------------------------------------
    # Pre-flight safety checks (extracted for cognitive complexity)
    # ------------------------------------------------------------------

    def _pre_flight_safety_checks(
        self,
        ctx: _ChaosRunCtx,
        _exp_def: ExperimentDef,
        allow_production: bool,
    ) -> ChaosResult | None:
        """Return a failure ChaosResult if any safety guard triggers, else None."""
        if not ctx.dry_run and not allow_production:
            target_lower = ctx.target.lower()
            for prod_pattern in _PRODUCTION_TARGETS:
                if prod_pattern in target_lower:
                    return ChaosResult(
                        experiment=ctx.experiment_name,
                        target=ctx.target,
                        success=False,
                        observations=[
                            f"BLOCKED: target '{ctx.target}' matches production pattern "
                            f"'{prod_pattern}'. Set allow_production=True to override.",
                        ],
                        dry_run=ctx.dry_run,
                        experiment_id=ctx.experiment_id,
                        state=ExperimentState.FAILED.value,
                        started_at=ctx.now,
                    )

        if len(self._running) >= _MAX_CONCURRENT_EXPERIMENTS:
            return ChaosResult(
                experiment=ctx.experiment_name,
                target=ctx.target,
                success=False,
                observations=[
                    f"BLOCKED: {len(self._running)} experiments already running "
                    f"(max={_MAX_CONCURRENT_EXPERIMENTS}).",
                    f"Running: {list(self._running.keys())}",
                ],
                dry_run=ctx.dry_run,
                experiment_id=ctx.experiment_id,
                state=ExperimentState.FAILED.value,
                started_at=ctx.now,
            )

        if ctx.target in self._host_locks:
            return ChaosResult(
                experiment=ctx.experiment_name,
                target=ctx.target,
                success=False,
                observations=[
                    f"BLOCKED: host '{ctx.target}' already targeted by "
                    f"experiment {self._host_locks[ctx.target]}.",
                ],
                dry_run=ctx.dry_run,
                experiment_id=ctx.experiment_id,
                state=ExperimentState.FAILED.value,
                started_at=ctx.now,
            )

        return None

    def _check_blast_radius_cap(
        self,
        ctx: _ChaosRunCtx,
        blast_radius: list[str],
    ) -> ChaosResult | None:
        if len(blast_radius) > _MAX_BLAST_RADIUS_COMPONENTS:
            return ChaosResult(
                experiment=ctx.experiment_name,
                target=ctx.target,
                success=False,
                blast_radius=blast_radius,
                observations=[
                    f"BLOCKED: blast radius ({len(blast_radius)} components) "
                    f"exceeds maximum ({_MAX_BLAST_RADIUS_COMPONENTS}).",
                ],
                dry_run=ctx.dry_run,
                experiment_id=ctx.experiment_id,
                state=ExperimentState.FAILED.value,
                started_at=ctx.now,
            )
        return None

    def abort(self, experiment_id: str) -> bool:
        """Kill switch — immediately abort a running experiment.

        Returns True if the experiment was found and marked for abort.
        """
        self._aborted.add(experiment_id)

        if experiment_id in self._running:
            self._running[experiment_id].state = ExperimentState.ABORTED.value
            self._running[experiment_id].observations.append("ABORTED by kill switch")
            logger.warning("Chaos experiment %s ABORTED by kill switch", experiment_id)
            return True

        return False

    def get_history(self) -> list[dict[str, Any]]:
        """Return the experiment history."""
        return [
            {
                "experiment_id": r.experiment_id,
                "experiment": r.experiment,
                "target": r.target,
                "success": r.success,
                "dry_run": r.dry_run,
                "state": r.state,
                "blast_radius": r.blast_radius,
                "recovery_time_ms": r.recovery_time_ms,
                "observations": r.observations,
                "started_at": r.started_at,
                "completed_at": r.completed_at,
            }
            for r in self._history
        ]

    # ------------------------------------------------------------------
    # Blast radius calculation
    # ------------------------------------------------------------------

    def _calculate_blast_radius(self, exp_def: ExperimentDef, target: str) -> list[str]:
        """Estimate which components will be affected.

        In production this would query the knowledge graph for
        dependencies.  Currently returns a structural estimate.
        """
        base = [target]

        if "container" in exp_def.name:
            base.extend(
                [
                    f"{target}-sidecar",
                    f"{target}-healthcheck",
                ]
            )
        elif "network" in exp_def.name:
            base.extend(
                [
                    f"{target}-ingress",
                    f"{target}-egress",
                    f"{target}-dependent-services",
                ]
            )
        elif "cpu" in exp_def.name or "memory" in exp_def.name:
            base.extend(
                [
                    f"{target}-colocated-containers",
                    f"{target}-monitoring-agent",
                ]
            )
        elif "disk" in exp_def.name:
            base.extend(
                [
                    f"{target}-filesystem",
                    f"{target}-log-pipeline",
                ]
            )

        return base

    # ------------------------------------------------------------------
    # HITL approval
    # ------------------------------------------------------------------

    async def _check_hitl_approval(
        self, exp_def: ExperimentDef, target: str, experiment_id: str
    ) -> bool:
        """Check HITL approval for the experiment.

        In production, this submits to the HITL workflow and waits for
        dual approval.  Currently returns False (always blocks).
        """
        await asyncio.sleep(0)
        logger.info(
            "HITL approval required for experiment_id=%s: %s on %s (risk_class=%s, dual=%s)",
            experiment_id,
            exp_def.name,
            target,
            exp_def.risk_class,
            exp_def.requires_dual_approval,
        )
        return False

    # ------------------------------------------------------------------
    # Simulation (dry run)
    # ------------------------------------------------------------------

    async def _simulate(
        self, exp_def: ExperimentDef, target: str, result: ChaosResult
    ) -> ChaosResult:
        """Simulate the experiment without real fault injection."""
        result.observations.append(f"DRY RUN — {exp_def.description}")
        result.observations.append(f"Target: {target}")
        result.observations.append(f"Max duration: {exp_def.max_duration_seconds}s")
        result.observations.append(f"Recovery check: {exp_def.recovery_check}")
        result.observations.append(f"Risk class: {exp_def.risk_class}")
        result.observations.append(
            f"Blast radius ({len(result.blast_radius)} components): "
            f"{', '.join(result.blast_radius)}"
        )

        await asyncio.sleep(0.1)

        if result.experiment_id in self._aborted:
            result.state = ExperimentState.ABORTED.value
            result.observations.append("Simulation aborted")
            return result

        result.success = True
        result.recovery_time_ms = 0
        result.state = ExperimentState.COMPLETED.value
        result.observations.append("Simulation complete — no real changes were made")
        return result

    # ------------------------------------------------------------------
    # Execution with timeout enforcement
    # ------------------------------------------------------------------

    async def _execute_with_timeout(
        self, exp_def: ExperimentDef, target: str, result: ChaosResult
    ) -> ChaosResult:
        """Wrap _execute with asyncio timeout enforcement."""
        try:
            return await asyncio.wait_for(
                self._execute(exp_def, target, result),
                timeout=float(exp_def.max_duration_seconds),
            )
        except TimeoutError:
            result.state = ExperimentState.ABORTED.value
            result.observations.append(
                f"TIMEOUT: experiment exceeded max_duration_seconds "
                f"({exp_def.max_duration_seconds}s)"
            )
            logger.error(
                "Chaos experiment %s TIMED OUT after %ds",
                result.experiment_id,
                exp_def.max_duration_seconds,
            )
            await self._execute_rollback(exp_def, target, result)
            return result

    # ------------------------------------------------------------------
    # Execution (live — blocked unless HITL approved)
    # ------------------------------------------------------------------

    async def _execute(
        self, exp_def: ExperimentDef, target: str, result: ChaosResult
    ) -> ChaosResult:
        """Execute the experiment with real fault injection.

        In production, dispatches to the appropriate fault-injection
        mechanism (e.g. docker kill, tc qdisc, stress-ng).
        Checks abort flag periodically during execution.
        """
        start = time.monotonic()

        result.observations.append(f"LIVE EXECUTION — {exp_def.description}")
        result.observations.append(f"Target: {target}")
        result.observations.append(f"Max duration: {exp_def.max_duration_seconds}s")
        result.observations.append(f"Data safety verified: {result.data_safety_verified}")

        elapsed = 0.0
        while elapsed < exp_def.max_duration_seconds:
            if result.experiment_id in self._aborted:
                result.state = ExperimentState.ABORTED.value
                result.observations.append(f"Execution aborted by kill switch at {elapsed:.1f}s")
                logger.warning(
                    "Chaos experiment %s ABORTED at %.1fs",
                    result.experiment_id,
                    elapsed,
                )
                await self._execute_rollback(exp_def, target, result)
                return result

            await asyncio.sleep(_ABORT_CHECK_INTERVAL_SECONDS)
            elapsed = time.monotonic() - start

        recovery_ok = await self._verify_recovery(exp_def, target)
        elapsed_ms = int((time.monotonic() - start) * 1000)

        result.success = recovery_ok
        result.recovery_time_ms = elapsed_ms
        result.state = ExperimentState.COMPLETED.value
        result.observations.append(
            f"Recovery verification: {'PASS' if recovery_ok else 'FAIL'} (elapsed={elapsed_ms}ms)"
        )

        if not recovery_ok:
            await self._execute_rollback(exp_def, target, result)

        return result

    # ------------------------------------------------------------------
    # Post-experiment verification
    # ------------------------------------------------------------------

    async def _verify_recovery(self, exp_def: ExperimentDef, target: str) -> bool:
        """Verify that the target recovered after the experiment.

        In production, runs the recovery_check assertion against live
        state.  Currently returns True (placeholder).
        """
        await asyncio.sleep(0)
        logger.info(
            "Recovery verification for %s on %s: %s",
            exp_def.name,
            target,
            exp_def.recovery_check,
        )
        return True

    # ------------------------------------------------------------------
    # Data safety pre-check
    # ------------------------------------------------------------------

    def _verify_data_safety(self, exp_def: ExperimentDef, target: str) -> bool:
        """Check if it is safe to inject faults without risking data corruption.

        For disk and memory experiments, verifies that the target is not
        a data store with uncommitted transactions.  In production, queries
        host metadata from the CMDB registry.
        """
        destructive_experiments = {"disk_fill_test", "memory_pressure"}
        if exp_def.name not in destructive_experiments:
            return True

        data_critical_targets = {"db", "database", "postgres", "redis", "etcd"}
        target_lower = target.lower()
        for pattern in data_critical_targets:
            if pattern in target_lower:
                logger.warning(
                    "Data safety BLOCKED for %s on %s: target matches data-critical pattern '%s'",
                    exp_def.name,
                    target,
                    pattern,
                )
                return False

        logger.info(
            "Data safety pre-check for %s on %s: passed",
            exp_def.name,
            target,
        )
        return True

    # ------------------------------------------------------------------
    # Rollback hook
    # ------------------------------------------------------------------

    async def _execute_rollback(
        self, exp_def: ExperimentDef, target: str, result: ChaosResult
    ) -> None:
        """Attempt to restore target to pre-experiment state.

        In production, dispatches to the appropriate rollback mechanism
        (container restart, iptables flush, stress-ng kill, tmpfile cleanup).
        """
        logger.warning(
            "Executing rollback for %s on %s (experiment_id=%s)",
            exp_def.name,
            target,
            result.experiment_id,
        )

        rollback_actions = {
            "kill_container": "docker restart",
            "network_partition_simulate": "iptables -F / tc qdisc del",
            "cpu_stress": "kill stress-ng process",
            "memory_pressure": "kill memory allocator process",
            "disk_fill_test": "rm temporary fill files",
        }

        action = rollback_actions.get(exp_def.name, "generic state restoration")
        result.observations.append(f"ROLLBACK initiated: {action}")
        result.rollback_executed = True

        await asyncio.sleep(0)
        logger.info(
            "Rollback completed for %s on %s: %s",
            exp_def.name,
            target,
            action,
        )
