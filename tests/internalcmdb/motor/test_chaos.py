"""Tests for internalcmdb.motor.chaos."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from internalcmdb.motor.chaos import (
    _MAX_BLAST_RADIUS_COMPONENTS,
    _MAX_CONCURRENT_EXPERIMENTS,
    EXPERIMENTS,
    ChaosEngine,
    ChaosResult,
    ExperimentState,
)

# ---------------------------------------------------------------------------
# Tests: EXPERIMENTS dict
# ---------------------------------------------------------------------------


class TestExperimentsDict:
    def test_experiments_has_five_entries(self) -> None:
        assert len(EXPERIMENTS) == 5

    def test_all_expected_experiments_present(self) -> None:
        expected = {
            "kill_container",
            "network_partition_simulate",
            "cpu_stress",
            "memory_pressure",
            "disk_fill_test",
        }
        assert set(EXPERIMENTS.keys()) == expected

    def test_all_experiments_have_risk_class(self) -> None:
        for name, exp in EXPERIMENTS.items():
            assert exp.risk_class in ("RC-3", "RC-4"), f"{name} has unexpected risk_class"

    def test_all_experiments_have_max_duration(self) -> None:
        for name, exp in EXPERIMENTS.items():
            assert exp.max_duration_seconds > 0, f"{name} has no max_duration"

    def test_dual_approval_required_for_network_partition(self) -> None:
        assert EXPERIMENTS["network_partition_simulate"].requires_dual_approval is True


# ---------------------------------------------------------------------------
# Tests: ChaosResult dataclass
# ---------------------------------------------------------------------------


class TestChaosResult:
    def test_defaults(self) -> None:
        r = ChaosResult(experiment="cpu_stress", target="host-01", success=True)
        assert r.dry_run is True
        assert r.blast_radius == []
        assert r.observations == []
        assert r.recovery_time_ms is None
        assert r.rollback_executed is False

    def test_custom_values(self) -> None:
        r = ChaosResult(
            experiment="kill_container",
            target="container-01",
            success=False,
            dry_run=False,
            state=ExperimentState.FAILED.value,
        )
        assert r.success is False
        assert r.dry_run is False
        assert r.state == "failed"


# ---------------------------------------------------------------------------
# Tests: run_experiment — dry_run
# ---------------------------------------------------------------------------


class TestChaosDryRun:
    @pytest.mark.asyncio
    async def test_dry_run_returns_result_with_dry_run_true(self) -> None:
        engine = ChaosEngine()
        result = await engine.run_experiment("cpu_stress", "dev-host-01", dry_run=True)

        assert isinstance(result, ChaosResult)
        assert result.dry_run is True
        assert result.experiment == "cpu_stress"
        assert result.target == "dev-host-01"

    @pytest.mark.asyncio
    async def test_dry_run_succeeds(self) -> None:
        engine = ChaosEngine()
        result = await engine.run_experiment("kill_container", "dev-host-02", dry_run=True)

        assert result.success is True
        assert result.state == ExperimentState.COMPLETED.value

    @pytest.mark.asyncio
    async def test_dry_run_adds_observations(self) -> None:
        engine = ChaosEngine()
        result = await engine.run_experiment("memory_pressure", "dev-host-03", dry_run=True)

        assert len(result.observations) > 0
        observations_text = " ".join(result.observations)
        assert "DRY RUN" in observations_text

    @pytest.mark.asyncio
    async def test_dry_run_populates_blast_radius(self) -> None:
        engine = ChaosEngine()
        result = await engine.run_experiment("cpu_stress", "dev-host-01", dry_run=True)

        assert isinstance(result.blast_radius, list)
        assert "dev-host-01" in result.blast_radius

    @pytest.mark.asyncio
    async def test_dry_run_timestamps_populated(self) -> None:
        engine = ChaosEngine()
        result = await engine.run_experiment("disk_fill_test", "dev-host-01", dry_run=True)

        assert result.started_at != ""
        assert result.completed_at != ""


# ---------------------------------------------------------------------------
# Tests: unknown experiment
# ---------------------------------------------------------------------------


class TestChaosUnknownExperiment:
    @pytest.mark.asyncio
    async def test_unknown_experiment_returns_failed_result(self) -> None:
        engine = ChaosEngine()
        result = await engine.run_experiment("nonexistent_experiment", "host-01", dry_run=True)

        assert result.success is False
        assert result.state == ExperimentState.FAILED.value

    @pytest.mark.asyncio
    async def test_unknown_experiment_observations_mention_name(self) -> None:
        engine = ChaosEngine()
        result = await engine.run_experiment("does_not_exist", "host-01", dry_run=True)

        obs_text = " ".join(result.observations)
        assert "does_not_exist" in obs_text or "Unknown" in obs_text

    @pytest.mark.asyncio
    async def test_unknown_experiment_lists_available(self) -> None:
        engine = ChaosEngine()
        result = await engine.run_experiment("fake_exp", "host-01", dry_run=True)

        obs_text = " ".join(result.observations)
        assert "kill_container" in obs_text or "Available" in obs_text


# ---------------------------------------------------------------------------
# Tests: production guard
# ---------------------------------------------------------------------------


class TestChaosProductionGuard:
    @pytest.mark.asyncio
    async def test_production_target_blocked_without_flag(self) -> None:
        engine = ChaosEngine()
        result = await engine.run_experiment(
            "cpu_stress", "prod", dry_run=False, allow_production=False
        )

        assert result.success is False
        obs_text = " ".join(result.observations)
        assert "BLOCKED" in obs_text or "production" in obs_text.lower()

    @pytest.mark.asyncio
    async def test_prod_gpu_target_blocked_without_flag(self) -> None:
        engine = ChaosEngine()
        result = await engine.run_experiment(
            "cpu_stress", "prod-gpu", dry_run=False, allow_production=False
        )

        assert result.success is False

    @pytest.mark.asyncio
    async def test_production_target_allowed_with_flag_but_hitl_blocks(self) -> None:
        engine = ChaosEngine()
        result = await engine.run_experiment(
            "cpu_stress", "prod", dry_run=False, allow_production=True
        )

        assert result.success is False
        obs_text = " ".join(result.observations)
        assert "HITL" in obs_text or "approval" in obs_text.lower() or "pending" in obs_text

    @pytest.mark.asyncio
    async def test_production_guard_skipped_in_dry_run(self) -> None:
        engine = ChaosEngine()
        result = await engine.run_experiment(
            "cpu_stress", "prod", dry_run=True, allow_production=False
        )

        assert result.dry_run is True
        assert result.success is True


# ---------------------------------------------------------------------------
# Tests: max concurrent experiments
# ---------------------------------------------------------------------------


class TestChaosMaxConcurrent:
    @pytest.mark.asyncio
    async def test_exceeding_max_concurrent_blocks(self) -> None:
        engine = ChaosEngine()

        for i in range(_MAX_CONCURRENT_EXPERIMENTS):
            engine._running[f"exp-{i}"] = MagicMock()

        result = await engine.run_experiment("cpu_stress", "host-01", dry_run=True)

        assert result.success is False
        obs_text = " ".join(result.observations)
        assert "BLOCKED" in obs_text

    @pytest.mark.asyncio
    async def test_exactly_at_limit_blocks(self) -> None:
        engine = ChaosEngine()

        for i in range(_MAX_CONCURRENT_EXPERIMENTS):
            engine._running[f"running-exp-{i}"] = MagicMock()

        result = await engine.run_experiment("kill_container", "host-02", dry_run=True)

        assert result.success is False


# ---------------------------------------------------------------------------
# Tests: blast radius cap
# ---------------------------------------------------------------------------


class TestChaosBlastRadiusCap:
    @pytest.mark.asyncio
    async def test_blast_radius_over_limit_blocks(self) -> None:
        engine = ChaosEngine()

        with patch.object(
            engine,
            "_calculate_blast_radius",
            return_value=[f"component-{i}" for i in range(_MAX_BLAST_RADIUS_COMPONENTS + 1)],
        ):
            result = await engine.run_experiment("cpu_stress", "host-01", dry_run=True)

        assert result.success is False
        obs_text = " ".join(result.observations)
        assert "BLOCKED" in obs_text or "blast radius" in obs_text.lower()

    @pytest.mark.asyncio
    async def test_blast_radius_at_limit_allowed(self) -> None:
        engine = ChaosEngine()

        with patch.object(
            engine,
            "_calculate_blast_radius",
            return_value=[f"component-{i}" for i in range(_MAX_BLAST_RADIUS_COMPONENTS)],
        ):
            result = await engine.run_experiment("cpu_stress", "host-01", dry_run=True)

        assert result.success is True


# ---------------------------------------------------------------------------
# Tests: abort
# ---------------------------------------------------------------------------


class TestChaosAbort:
    def test_abort_adds_to_aborted_set(self) -> None:
        engine = ChaosEngine()
        result = engine.abort("exp-unknown")

        assert "exp-unknown" in engine._aborted
        assert result is False

    def test_abort_running_experiment_returns_true(self) -> None:
        engine = ChaosEngine()
        mock_result = MagicMock()
        mock_result.state = ExperimentState.RUNNING.value
        mock_result.observations = []
        engine._running["exp-active"] = mock_result

        ok = engine.abort("exp-active")

        assert ok is True
        assert mock_result.state == ExperimentState.ABORTED.value
        assert "ABORTED" in mock_result.observations[-1]

    @pytest.mark.asyncio
    async def test_aborted_experiment_detected_during_simulation(self) -> None:
        engine = ChaosEngine()

        original_simulate = engine._simulate

        async def _simulate_and_abort(exp_def, target, result):
            engine._aborted.add(result.experiment_id)
            return await original_simulate(exp_def, target, result)

        with patch.object(engine, "_simulate", side_effect=_simulate_and_abort):
            result = await engine.run_experiment("cpu_stress", "host-01", dry_run=True)

        assert result.state == ExperimentState.ABORTED.value


# ---------------------------------------------------------------------------
# Tests: per-host lock
# ---------------------------------------------------------------------------


class TestChaosPerHostLock:
    @pytest.mark.asyncio
    async def test_same_host_blocked_while_running(self) -> None:
        engine = ChaosEngine()
        engine._host_locks["host-01"] = "existing-exp-id"

        result = await engine.run_experiment("cpu_stress", "host-01", dry_run=True)

        assert result.success is False
        obs_text = " ".join(result.observations)
        assert "BLOCKED" in obs_text

    @pytest.mark.asyncio
    async def test_different_host_not_blocked(self) -> None:
        engine = ChaosEngine()
        engine._host_locks["host-01"] = "existing-exp-id"

        result = await engine.run_experiment("cpu_stress", "host-02", dry_run=True)

        assert result.success is True

    @pytest.mark.asyncio
    async def test_host_lock_released_after_run(self) -> None:
        engine = ChaosEngine()
        await engine.run_experiment("cpu_stress", "host-03", dry_run=True)

        assert "host-03" not in engine._host_locks


# ---------------------------------------------------------------------------
# Tests: get_history
# ---------------------------------------------------------------------------


class TestGetHistory:
    @pytest.mark.asyncio
    async def test_history_recorded_after_run(self) -> None:
        engine = ChaosEngine()
        await engine.run_experiment("cpu_stress", "host-01", dry_run=True)

        history = engine.get_history()

        assert len(history) == 1
        assert history[0]["experiment"] == "cpu_stress"
        assert history[0]["target"] == "host-01"
        assert history[0]["dry_run"] is True
