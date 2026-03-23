"""Tests for internalcmdb.seeds.shared_service_seed — S1192 literal dedup.

Covers:
  - Host hint constants defined and used instead of raw IP literals
  - All services in catalogue have consistent metadata
  - No duplicate service_code values
  - Seed function signature is correct
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from internalcmdb.seeds.shared_service_seed import (
    _HOST_HZ_113,
    _HOST_ORCHESTRATOR,
    _SERVICES,
    seed,
)


_SEED_PATH = Path("src/internalcmdb/seeds/shared_service_seed.py")


class TestHostConstants:
    """S1192: IP literals must be extracted into constants."""

    def test_orchestrator_constant_value(self) -> None:
        assert _HOST_ORCHESTRATOR == "77.42.76.185 (orchestrator)"

    def test_hz113_constant_value(self) -> None:
        assert _HOST_HZ_113 == "49.13.97.113 (hz.113)"

    def test_no_raw_orchestrator_ip_in_host_hint(self) -> None:
        """No raw '77.42.76.185 (orchestrator)' strings in host_hint assignments."""
        content = _SEED_PATH.read_text()
        raw_matches = re.findall(
            r'"host_hint":\s*"77\.42\.76\.185 \(orchestrator\)"', content
        )
        assert len(raw_matches) == 0, (
            f"Found {len(raw_matches)} raw orchestrator IP literals — "
            "use _HOST_ORCHESTRATOR constant"
        )

    def test_no_raw_hz113_ip_in_host_hint(self) -> None:
        content = _SEED_PATH.read_text()
        raw_matches = re.findall(
            r'"host_hint":\s*"49\.13\.97\.113 \(hz\.113\)"', content
        )
        assert len(raw_matches) == 0, (
            f"Found {len(raw_matches)} raw hz.113 IP literals — "
            "use _HOST_HZ_113 constant"
        )

    def test_constant_used_in_orchestrator_services(self) -> None:
        content = _SEED_PATH.read_text()
        uses = content.count("_HOST_ORCHESTRATOR")
        assert uses >= 15, (
            f"Expected _HOST_ORCHESTRATOR used at least 15 times, found {uses}"
        )


class TestServiceCatalogue:
    """Validate the service catalogue data integrity."""

    def test_all_services_have_required_fields(self) -> None:
        for svc in _SERVICES:
            code, name, kind, env, lifecycle, _desc, meta = svc
            assert isinstance(code, str) and len(code) > 0
            assert isinstance(name, str) and len(name) > 0
            assert isinstance(kind, str)
            assert isinstance(env, str)
            assert isinstance(lifecycle, str)
            assert isinstance(meta, dict)

    def test_no_duplicate_service_codes(self) -> None:
        codes = [svc[0] for svc in _SERVICES]
        assert len(codes) == len(set(codes)), (
            f"Duplicate service codes: {[c for c in codes if codes.count(c) > 1]}"
        )

    def test_all_metadata_have_category(self) -> None:
        for svc in _SERVICES:
            meta = svc[6]
            assert "category" in meta, (
                f"Service '{svc[0]}' missing 'category' in metadata"
            )

    def test_orchestrator_services_use_constant(self) -> None:
        orchestrator_ip = _HOST_ORCHESTRATOR.split(" ")[0]
        for svc in _SERVICES:
            meta = svc[6]
            host_hint = meta.get("host_hint", "")
            if orchestrator_ip in str(host_hint):
                assert host_hint == _HOST_ORCHESTRATOR, (
                    f"Service '{svc[0]}' has raw IP instead of _HOST_ORCHESTRATOR"
                )

    def test_service_count(self) -> None:
        assert len(_SERVICES) >= 20, (
            f"Expected at least 20 services, got {len(_SERVICES)}"
        )

    def test_seed_function_callable(self) -> None:
        assert callable(seed)
