"""Tests for individual collector modules — collect() functions."""

from __future__ import annotations

import importlib
import subprocess
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# All collector module names (19 modules matching COLLECTOR_MODULES)
# ---------------------------------------------------------------------------

ALL_COLLECTOR_MODULE_NAMES = [
    "heartbeat",
    "system_vitals",
    "docker_state",
    "container_resources",
    "gpu_state",
    "vllm_metrics",
    "llm_endpoint_health",
    "service_health",
    "network_state",
    "network_latency",
    "disk_state",
    "process_inventory",
    "systemd_state",
    "journal_errors",
    "trust_surface_lite",
    "certificate_state",
    "security_posture",
    "full_hardware",
    "full_audit",
]

_BASE_PACKAGE = "internalcmdb.collectors.agent.collectors"


def _import_collector(name: str):
    return importlib.import_module(f"{_BASE_PACKAGE}.{name}")


# ---------------------------------------------------------------------------
# heartbeat
# ---------------------------------------------------------------------------


class TestHeartbeatCollect:
    def test_heartbeat_collect_returns_dict(self):
        mod = _import_collector("heartbeat")
        with (
            patch("os.getloadavg", return_value=(0.5, 0.6, 0.7)),
            patch("builtins.open", side_effect=FileNotFoundError),
            patch("subprocess.run") as mock_run,
        ):
            mock_result = MagicMock()
            mock_result.stdout = "{ sec = 1700000000, usec = 0 }"
            mock_run.return_value = mock_result
            result = mod.collect()

        assert isinstance(result, dict)
        assert "uptime_seconds" in result
        assert "load_avg" in result
        assert "memory_pct" in result

    def test_heartbeat_collect_keys(self):
        mod = _import_collector("heartbeat")
        with (
            patch("os.getloadavg", return_value=(1.0, 1.0, 1.0)),
            patch("builtins.open", side_effect=FileNotFoundError),
            patch("subprocess.run") as mock_run,
        ):
            mock_result = MagicMock()
            mock_result.stdout = "{ sec = 1700000000, usec = 0 }"
            mock_run.return_value = mock_result
            result = mod.collect()

        assert isinstance(result["load_avg"], list)
        assert len(result["load_avg"]) == 3
        assert isinstance(result["uptime_seconds"], float)

    def test_heartbeat_collect_with_proc_files(self):
        mod = _import_collector("heartbeat")
        uptime_content = "12345.67 23456.78\n"
        meminfo_content = "MemTotal: 8192000 kB\nMemAvailable: 4096000 kB\n"

        def open_mock(path, *args, **kwargs):
            handle = MagicMock()
            path_str = str(path)
            if "uptime" in path_str:
                handle.__enter__ = lambda s: MagicMock(read=lambda: uptime_content)
            elif "meminfo" in path_str:
                handle.__enter__ = lambda s: MagicMock(read=lambda: meminfo_content)
            else:
                handle.__enter__ = lambda s: MagicMock(read=lambda: "")
            handle.__exit__ = MagicMock(return_value=False)
            return handle

        with (
            patch("builtins.open", side_effect=open_mock),
            patch("os.getloadavg", return_value=(0.1, 0.2, 0.3)),
        ):
            result = mod.collect()

        assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# system_vitals
# ---------------------------------------------------------------------------


class TestSystemVitalsCollect:
    def test_system_vitals_collect_returns_dict(self):
        mod = _import_collector("system_vitals")
        with (
            patch("os.getloadavg", return_value=(0.5, 0.8, 1.0)),
            patch("builtins.open", side_effect=FileNotFoundError),
        ):
            result = mod.collect()

        assert isinstance(result, dict)
        assert "load_avg" in result
        assert "cpu_times" in result
        assert "memory_kb" in result

    def test_system_vitals_contains_swap_keys(self):
        mod = _import_collector("system_vitals")
        with (
            patch("os.getloadavg", return_value=(0.1, 0.2, 0.3)),
            patch("builtins.open", side_effect=FileNotFoundError),
        ):
            result = mod.collect()

        assert "swap_total_kb" in result
        assert "swap_free_kb" in result

    def test_system_vitals_load_avg_list(self):
        mod = _import_collector("system_vitals")
        with (
            patch("os.getloadavg", return_value=(1.5, 2.0, 2.5)),
            patch("builtins.open", side_effect=FileNotFoundError),
        ):
            result = mod.collect()

        assert isinstance(result["load_avg"], list)
        assert len(result["load_avg"]) == 3


# ---------------------------------------------------------------------------
# disk_state
# ---------------------------------------------------------------------------


class TestDiskStateCollect:
    def test_disk_state_collect_returns_dict(self):
        mod = _import_collector("disk_state")
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = (
            "Filesystem         Mounted on  1B-blocks     Used Available Use%\n"
            "/dev/sda1          /           10000000  5000000   5000000  50%\n"
        )

        with patch("subprocess.run", return_value=mock_result):
            result = mod.collect()

        assert isinstance(result, dict)
        assert "disks" in result
        assert "total" in result

    def test_disk_state_collect_no_df(self):
        mod = _import_collector("disk_state")
        with patch("subprocess.run", side_effect=FileNotFoundError):
            result = mod.collect()

        assert isinstance(result, dict)
        assert result["disks"] == []
        assert "error" in result

    def test_disk_state_collect_timeout(self):
        mod = _import_collector("disk_state")
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("df", 5)):
            result = mod.collect()

        assert isinstance(result, dict)
        assert result["disks"] == []

    def test_disk_state_collect_disks_list(self):
        mod = _import_collector("disk_state")
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = (
            "Filesystem 1B-blocks Used Avail Use% Mounted\n"
            "/dev/sda1  104857600 52428800 52428800 50% /\n"
        )

        with patch("subprocess.run", return_value=mock_result):
            result = mod.collect()

        assert isinstance(result["disks"], list)
        assert isinstance(result["total"], int)


# ---------------------------------------------------------------------------
# docker_state
# ---------------------------------------------------------------------------


class TestDockerStateCollect:
    def test_docker_state_collect_returns_dict(self):
        mod = _import_collector("docker_state")
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = (
            '{"name":"web","image":"nginx","status":"Up 2h",'
            '"ports":"80/tcp","created":"2024-01-01","id":"abc123"}\n'
        )

        with patch("subprocess.run", return_value=mock_result):
            result = mod.collect()

        assert isinstance(result, dict)
        assert "containers" in result
        assert "total" in result

    def test_docker_state_collect_no_docker(self):
        mod = _import_collector("docker_state")
        with patch("subprocess.run", side_effect=FileNotFoundError):
            result = mod.collect()

        assert result["containers"] == []
        assert "error" in result
        assert result["error"] == "docker not found"

    def test_docker_state_collect_timeout(self):
        mod = _import_collector("docker_state")
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("docker", 10)):
            result = mod.collect()

        assert result["containers"] == []
        assert result["error"] == "timeout"

    def test_docker_state_collect_nonzero_returncode(self):
        mod = _import_collector("docker_state")
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "permission denied"
        mock_result.stdout = ""

        with patch("subprocess.run", return_value=mock_result):
            result = mod.collect()

        assert result["containers"] == []
        assert "error" in result

    def test_docker_state_collect_empty_output(self):
        mod = _import_collector("docker_state")
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""

        with patch("subprocess.run", return_value=mock_result):
            result = mod.collect()

        assert result["containers"] == []
        assert result["total"] == 0


# ---------------------------------------------------------------------------
# gpu_state
# ---------------------------------------------------------------------------


class TestGpuStateCollect:
    def test_gpu_state_collect_no_nvidia_smi(self):
        mod = _import_collector("gpu_state")
        with patch("subprocess.run", side_effect=FileNotFoundError):
            result = mod.collect()

        assert isinstance(result, dict)
        assert result["gpus"] == []
        assert "error" in result

    def test_gpu_state_collect_returns_dict(self):
        mod = _import_collector("gpu_state")
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "0, Tesla T4, 16160, 1024, 15136, 5, 10, 35, 50.5, 150.0\n"

        with patch("subprocess.run", return_value=mock_result):
            result = mod.collect()

        assert isinstance(result, dict)
        assert "gpus" in result
        assert "total" in result

    def test_gpu_state_collect_nonzero_returncode(self):
        mod = _import_collector("gpu_state")
        mock_result = MagicMock()
        mock_result.returncode = 6
        mock_result.stderr = "NVIDIA-SMI has failed"
        mock_result.stdout = ""

        with patch("subprocess.run", return_value=mock_result):
            result = mod.collect()

        assert result["gpus"] == []
        assert "error" in result

    def test_gpu_state_collect_timeout(self):
        mod = _import_collector("gpu_state")
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("nvidia-smi", 10)):
            result = mod.collect()

        assert result["gpus"] == []
        assert result["error"] == "timeout"

    def test_gpu_state_collect_parses_gpu_fields(self):
        mod = _import_collector("gpu_state")
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "0, NVIDIA A100, 40960, 2048, 38912, 15, 8, 42, 120.0, 400.0\n"

        with patch("subprocess.run", return_value=mock_result):
            result = mod.collect()

        assert result["total"] == 1
        gpu = result["gpus"][0]
        assert gpu["index"] == 0
        assert "memory_total_mb" in gpu
        assert "utilization_gpu_pct" in gpu
        assert "temperature_celsius" in gpu


# ---------------------------------------------------------------------------
# All modules have collect() function
# ---------------------------------------------------------------------------


class TestAllModulesHaveCollectFunction:
    def test_all_modules_have_collect_function(self):
        for name in ALL_COLLECTOR_MODULE_NAMES:
            mod = _import_collector(name)
            assert hasattr(mod, "collect"), f"Module {name} missing collect()"
            assert callable(mod.collect), f"Module {name}.collect is not callable"

    def test_all_modules_count(self):
        assert len(ALL_COLLECTOR_MODULE_NAMES) == 19

    def test_collect_functions_return_dicts(self):
        """Smoke-test: call collect() on modules that are safe to call without I/O mocking."""
        safe_modules = ["heartbeat", "system_vitals", "disk_state", "docker_state", "gpu_state"]
        for name in safe_modules:
            mod = _import_collector(name)
            with (
                patch("subprocess.run") as mock_run,
                patch("os.getloadavg", return_value=(0.0, 0.0, 0.0)),
                patch("builtins.open", side_effect=FileNotFoundError),
            ):
                mock_result = MagicMock()
                mock_result.returncode = 1
                mock_result.stdout = ""
                mock_result.stderr = "not found"
                mock_run.return_value = mock_result
                result = mod.collect()

            assert isinstance(result, dict), f"{name}.collect() did not return a dict"
