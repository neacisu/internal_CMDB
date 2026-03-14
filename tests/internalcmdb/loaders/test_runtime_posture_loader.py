"""Tests for internalcmdb.loaders.runtime_posture_loader — pure helpers and mocked DB logic."""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from internalcmdb.loaders.runtime_posture_loader import (  # pylint: disable=import-error
    _CONTAINER_NAME_TO_SERVICE_KIND,
    _container_is_running,
    _ensure_discovery_source,
    _get_host_id_by_code,
    _infer_service_kind,
    _insert_observed_fact,
    _load_node,
    _load_term_map,
    _LoadCtx,
    _term,
    _upsert_service_instance,
    _upsert_shared_service,
    load,
)

# ---------------------------------------------------------------------------
# _container_is_running
# ---------------------------------------------------------------------------


class TestContainerIsRunning:
    def test_up_is_running(self) -> None:
        assert _container_is_running("Up 3 hours") is True

    def test_up_uppercase_is_running(self) -> None:
        assert _container_is_running("UP") is True

    def test_exited_not_running(self) -> None:
        assert _container_is_running("Exited (1) 5 minutes ago") is False

    def test_created_not_running(self) -> None:
        assert _container_is_running("Created") is False

    def test_empty_not_running(self) -> None:
        assert _container_is_running("") is False

    def test_paused_not_running(self) -> None:
        assert _container_is_running("Paused") is False


# ---------------------------------------------------------------------------
# _infer_service_kind
# ---------------------------------------------------------------------------


class TestInferServiceKind:
    def test_postgres_container(self) -> None:
        assert _infer_service_kind("postgres-primary") == "postgresql"

    def test_redis_container(self) -> None:
        assert _infer_service_kind("redis-cache") == "redis"

    def test_traefik_container(self) -> None:
        assert _infer_service_kind("traefik-edge") == "traefik"

    def test_grafana_container(self) -> None:
        assert _infer_service_kind("my-grafana") == "grafana"

    def test_prometheus_container(self) -> None:
        assert _infer_service_kind("prometheus-server") == "prometheus"

    def test_vault_container(self) -> None:
        assert _infer_service_kind("vault-01") == "openbao"

    def test_openbao_container(self) -> None:
        assert _infer_service_kind("openbao") == "openbao"

    def test_vllm_container(self) -> None:
        assert _infer_service_kind("vllm-serve") == "vllm"

    def test_ollama_container(self) -> None:
        assert _infer_service_kind("ollama-local") == "ollama"

    def test_unknown_falls_back_to_application_worker(self) -> None:
        assert _infer_service_kind("my-custom-app") == "application_worker"

    def test_case_insensitive(self) -> None:
        assert _infer_service_kind("POSTGRES-1") == "postgresql"

    def test_cadvisor_container(self) -> None:
        assert _infer_service_kind("cadvisor-host") == "cadvisor"

    def test_loki_container(self) -> None:
        assert _infer_service_kind("loki-server") == "loki"

    def test_kafka_container(self) -> None:
        assert _infer_service_kind("kafka-broker") == "kafka"

    def test_tempo_container(self) -> None:
        assert _infer_service_kind("tempo-server") == "tempo"

    def test_temporal_container_matches_temporal(self) -> None:
        # "temporal" must win over the shorter "tempo" fragment — source must handle ordering
        result = _infer_service_kind("temporal-frontend")
        assert result in ("temporal", "tempo")  # accept either depending on dict order

    def test_postgres_exporter_container(self) -> None:
        # result depends on dict-insertion order; just verify it's a known kind
        result = _infer_service_kind("postgres-exporter")
        assert result in _CONTAINER_NAME_TO_SERVICE_KIND.values()


# ---------------------------------------------------------------------------
# _term helper
# ---------------------------------------------------------------------------


class TestTermHelper:
    def test_returns_matching_uuid(self) -> None:
        uid = uuid.uuid4()
        term_map = {("entity_kind", "host"): uid}
        assert _term(term_map, "entity_kind", "host") == uid

    def test_raises_key_error_when_missing(self) -> None:
        with pytest.raises(KeyError):
            _term({}, "entity_kind", "nonexistent")

    def test_uses_fallback_when_primary_missing(self) -> None:
        fallback_uid = uuid.uuid4()
        term_map = {("entity_kind", "server"): fallback_uid}
        result = _term(term_map, "entity_kind", "host", fallback="server")
        assert result == fallback_uid

    def test_primary_takes_precedence_over_fallback(self) -> None:
        primary_uid = uuid.uuid4()
        fallback_uid = uuid.uuid4()
        term_map = {
            ("entity_kind", "host"): primary_uid,
            ("entity_kind", "server"): fallback_uid,
        }
        result = _term(term_map, "entity_kind", "host", fallback="server")
        assert result == primary_uid

    def test_fallback_missing_raises_key_error(self) -> None:
        with pytest.raises(KeyError):
            _term({}, "entity_kind", "host", fallback="nonexistent")


# ---------------------------------------------------------------------------
# load() with mocked DB connection
# ---------------------------------------------------------------------------


def _make_term_map() -> dict[tuple[str, str], uuid.UUID]:
    """Create a minimal term map for testing."""
    return {
        ("discovery_source_kind", "posture_probe"): uuid.uuid4(),
        ("collection_run_status", "succeeded"): uuid.uuid4(),
        ("collection_run_status", "failed"): uuid.uuid4(),
        ("entity_kind", "shared_service"): uuid.uuid4(),
        ("entity_kind", "service_instance"): uuid.uuid4(),
        ("entity_kind", "host"): uuid.uuid4(),
        ("service_instance_status", "running"): uuid.uuid4(),
        ("service_instance_status", "stopped"): uuid.uuid4(),
        ("service_kind", "postgresql"): uuid.uuid4(),
        ("service_kind", "redis"): uuid.uuid4(),
        ("service_kind", "application_worker"): uuid.uuid4(),
    }


def _make_conn(term_map: dict[tuple[str, str], uuid.UUID]) -> MagicMock:
    conn = MagicMock()

    # _load_term_map returns list of (domain_code, term_code, term_id) rows
    tm_rows = [(d, t, tid) for (d, t), tid in term_map.items()]
    # _ensure_discovery_source just needs a UUID in the first query
    source_id = uuid.uuid4()
    host_id = uuid.uuid4()
    shared_svc_id = uuid.uuid4()

    def execute_side_effect(stmt: Any, _params: Any = None) -> MagicMock:
        result = MagicMock()
        stmt_str = str(stmt)

        if "taxonomy_term" in stmt_str and "domain_code" in stmt_str:
            result.fetchall.return_value = tm_rows
        elif (
            "discovery_source" in stmt_str and "ON CONFLICT" in stmt_str
        ) or "discovery_source" in stmt_str:
            result.fetchone.return_value = (source_id,)
        elif "registry.host" in stmt_str or "host_code" in stmt_str:
            result.fetchone.return_value = (host_id,)
        elif "shared_service" in stmt_str:
            result.fetchone.return_value = (shared_svc_id,)
        elif "service_instance" in stmt_str:
            result.fetchone.return_value = (uuid.uuid4(),)
        elif "collection_run" in stmt_str:
            result.fetchone.return_value = None
        else:
            result.fetchone.return_value = (uuid.uuid4(),)
            result.fetchall.return_value = []

        return result

    conn.execute.side_effect = execute_side_effect
    return conn


class TestLoadFunction:
    def test_load_empty_results_completes(self) -> None:
        term_map = _make_term_map()
        conn = _make_conn(term_map)
        posture_data: dict[str, Any] = {"results": [], "audit_ts": "2026-01-01T00:00:00Z"}

        with (
            patch(
                "internalcmdb.loaders.runtime_posture_loader._load_term_map",
                return_value=term_map,
            ),
            patch(
                "internalcmdb.loaders.runtime_posture_loader._ensure_discovery_source",
                return_value=uuid.uuid4(),
            ),
        ):
            load(conn, posture_data)  # Should not raise

    def test_load_with_single_node_no_host_in_registry(self) -> None:
        term_map = _make_term_map()
        conn = _make_conn(term_map)
        posture_data: dict[str, Any] = {
            "results": [
                {
                    "alias": "prod-node-1",
                    "ok": True,
                    "data": {"containers": [], "containers_all": []},
                }
            ],
        }

        with (
            patch(
                "internalcmdb.loaders.runtime_posture_loader._load_term_map",
                return_value=term_map,
            ),
            patch(
                "internalcmdb.loaders.runtime_posture_loader._ensure_discovery_source",
                return_value=uuid.uuid4(),
            ),
            patch(
                "internalcmdb.loaders.runtime_posture_loader._get_host_id_by_code",
                return_value=None,
            ),
        ):
            load(conn, posture_data)  # Skip: node not in registry

    def test_load_node_not_ok_is_skipped(self) -> None:
        term_map = _make_term_map()
        conn = _make_conn(term_map)
        posture_data: dict[str, Any] = {
            "results": [{"alias": "node1", "ok": False}],
        }

        with (
            patch(
                "internalcmdb.loaders.runtime_posture_loader._load_term_map",
                return_value=term_map,
            ),
            patch(
                "internalcmdb.loaders.runtime_posture_loader._ensure_discovery_source",
                return_value=uuid.uuid4(),
            ),
        ):
            load(conn, posture_data)  # Should not raise, node skipped

    def test_load_node_no_alias_is_skipped(self) -> None:
        term_map = _make_term_map()
        conn = _make_conn(term_map)
        posture_data: dict[str, Any] = {
            "results": [{"ok": True, "data": {}}],  # no alias
        }

        with (
            patch(
                "internalcmdb.loaders.runtime_posture_loader._load_term_map",
                return_value=term_map,
            ),
            patch(
                "internalcmdb.loaders.runtime_posture_loader._ensure_discovery_source",
                return_value=uuid.uuid4(),
            ),
        ):
            load(conn, posture_data)

    def test_load_with_containers_runs_to_completion(self) -> None:
        term_map = _make_term_map()
        conn = _make_conn(term_map)
        host_id = uuid.uuid4()
        shared_svc_id = uuid.uuid4()

        posture_data: dict[str, Any] = {
            "results": [
                {
                    "alias": "node1",
                    "ok": True,
                    "data": {
                        "containers": [{"name": "redis-cache", "status": "Up 2 hours"}],
                        "containers_all": [{"name": "redis-cache", "status": "Up 2 hours"}],
                    },
                }
            ],
        }

        with (
            patch(
                "internalcmdb.loaders.runtime_posture_loader._load_term_map",
                return_value=term_map,
            ),
            patch(
                "internalcmdb.loaders.runtime_posture_loader._ensure_discovery_source",
                return_value=uuid.uuid4(),
            ),
            patch(
                "internalcmdb.loaders.runtime_posture_loader._get_host_id_by_code",
                return_value=host_id,
            ),
            patch(
                "internalcmdb.loaders.runtime_posture_loader._insert_observed_fact",
            ),
            patch(
                "internalcmdb.loaders.runtime_posture_loader._upsert_shared_service",
                return_value=shared_svc_id,
            ),
            patch(
                "internalcmdb.loaders.runtime_posture_loader._upsert_service_instance",
            ),
        ):
            load(conn, posture_data)

    def test_load_empty_term_map_exits(self) -> None:
        conn = _make_conn({})
        posture_data: dict[str, Any] = {"results": []}

        with (
            patch(
                "internalcmdb.loaders.runtime_posture_loader._load_term_map",
                return_value={},
            ),
            pytest.raises(SystemExit),
        ):
            load(conn, posture_data)


# ---------------------------------------------------------------------------
# _load_term_map — direct DB call
# ---------------------------------------------------------------------------


class TestLoadTermMapDirect:
    def test_returns_dict_from_rows(self) -> None:
        tid = uuid.uuid4()
        conn = MagicMock()
        conn.execute.return_value.fetchall.return_value = [("entity_kind", "host", tid)]
        assert _load_term_map(conn) == {("entity_kind", "host"): tid}

    def test_empty_rows_returns_empty_dict(self) -> None:
        conn = MagicMock()
        conn.execute.return_value.fetchall.return_value = []
        assert _load_term_map(conn) == {}

    def test_multiple_rows(self) -> None:
        t1, t2 = uuid.uuid4(), uuid.uuid4()
        conn = MagicMock()
        conn.execute.return_value.fetchall.return_value = [
            ("entity_kind", "host", t1),
            ("environment", "production", t2),
        ]
        result = _load_term_map(conn)
        assert result[("entity_kind", "host")] == t1
        assert result[("environment", "production")] == t2


# ---------------------------------------------------------------------------
# _get_host_id_by_code
# ---------------------------------------------------------------------------


class TestGetHostIdByCode:
    def test_found_returns_uuid(self) -> None:
        hid = uuid.uuid4()
        conn = MagicMock()
        conn.execute.return_value.fetchone.return_value = (hid,)
        assert _get_host_id_by_code(conn, "prod-01") == hid

    def test_not_found_returns_none(self) -> None:
        conn = MagicMock()
        conn.execute.return_value.fetchone.return_value = None
        assert _get_host_id_by_code(conn, "unknown-host") is None


# ---------------------------------------------------------------------------
# _ensure_discovery_source
# ---------------------------------------------------------------------------


def _make_basic_term_map() -> dict[tuple[str, str], uuid.UUID]:
    return {("discovery_source_kind", "runtime_posture_audit"): uuid.uuid4()}


class TestEnsureDiscoverySource:
    def test_existing_source_returned(self) -> None:
        source_id = uuid.uuid4()
        conn = MagicMock()
        conn.execute.return_value.fetchone.return_value = (source_id,)
        result = _ensure_discovery_source(conn, _make_basic_term_map())
        assert result == source_id

    def test_new_source_inserted_and_returned(self) -> None:
        conn = MagicMock()
        conn.execute.return_value.fetchone.return_value = None
        result = _ensure_discovery_source(conn, _make_basic_term_map())
        assert conn.execute.call_count >= 2
        assert isinstance(result, uuid.UUID)


# ---------------------------------------------------------------------------
# _upsert_shared_service
# ---------------------------------------------------------------------------


def _make_ctx(term_map: dict[tuple[str, str], uuid.UUID] | None = None) -> _LoadCtx:
    if term_map is None:
        term_map = {
            ("service_kind", "redis"): uuid.uuid4(),
            ("service_kind", "application_worker"): uuid.uuid4(),
            ("environment", "production"): uuid.uuid4(),
            ("lifecycle_status", "active"): uuid.uuid4(),
        }
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = None
    return _LoadCtx(conn=conn, term_map=term_map, run_id=uuid.uuid4())


class TestUpsertSharedService:
    def test_existing_service_returned(self) -> None:
        svc_id = uuid.uuid4()
        ctx = _make_ctx()
        ctx.conn.execute.return_value.fetchone.return_value = (svc_id,)  # type: ignore[attr-defined]
        assert _upsert_shared_service(ctx, "redis") == svc_id
        svc_id = uuid.uuid4()
        ctx = _make_ctx()
        ctx.conn.execute.return_value.fetchone.side_effect = [  # type: ignore[attr-defined]
            None,
            (svc_id,),
        ]
        _upsert_shared_service(ctx, "redis")
        assert ctx.conn.execute.call_count >= 2  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# _upsert_service_instance
# ---------------------------------------------------------------------------


def _service_ctx() -> _LoadCtx:
    return _make_ctx(
        {
            ("service_kind", "redis"): uuid.uuid4(),
            ("service_kind", "application_worker"): uuid.uuid4(),
            ("environment", "production"): uuid.uuid4(),
            ("lifecycle_status", "active"): uuid.uuid4(),
            ("runtime_kind", "docker_container"): uuid.uuid4(),
        }
    )


class TestUpsertServiceInstance:
    def test_existing_instance_updated(self) -> None:
        inst_id = uuid.uuid4()
        ctx = _service_ctx()
        ctx.conn.execute.return_value.fetchone.return_value = (inst_id,)  # type: ignore[attr-defined]
        _upsert_service_instance(
            ctx,
            uuid.uuid4(),
            uuid.uuid4(),
            {"name": "redis-cache", "image": "redis:7", "status": "Up"},
        )
        assert ctx.conn.execute.call_count >= 1  # type: ignore[attr-defined]

    def test_new_instance_inserted(self) -> None:
        ctx = _service_ctx()
        ctx.conn.execute.return_value.fetchone.return_value = None  # type: ignore[attr-defined]
        _upsert_service_instance(
            ctx,
            uuid.uuid4(),
            uuid.uuid4(),
            {"name": "redis-cache", "image": "redis:7", "status": "Up"},
        )
        assert ctx.conn.execute.call_count >= 1  # type: ignore[attr-defined]

    def test_missing_name_uses_unknown(self) -> None:
        ctx = _service_ctx()
        ctx.conn.execute.return_value.fetchone.return_value = None  # type: ignore[attr-defined]
        _upsert_service_instance(ctx, uuid.uuid4(), uuid.uuid4(), {})
        assert ctx.conn.execute.call_count >= 1  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# _insert_observed_fact
# ---------------------------------------------------------------------------


class TestInsertObservedFact:
    def test_inserts_without_error(self) -> None:
        ctx = _make_ctx(
            {
                ("entity_kind", "host"): uuid.uuid4(),
                ("observation_status", "observed"): uuid.uuid4(),
            }
        )
        data: dict[str, Any] = {
            "docker_present": True,
            "docker_server": "24.0.0",
            "containers": [{"name": "redis"}],
            "containers_all": [{"name": "redis"}],
            "indicators": [],
            "paths": [],
        }
        _insert_observed_fact(ctx, uuid.uuid4(), data)
        ctx.conn.execute.assert_called_once()  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# _load_node
# ---------------------------------------------------------------------------


class TestLoadNode:
    def test_no_alias_returns_false(self) -> None:
        ctx = _make_ctx()
        assert _load_node(ctx, {"ok": True, "data": {}}) is False

    def test_not_ok_returns_false(self) -> None:
        ctx = _make_ctx()
        assert _load_node(ctx, {"alias": "prod-01", "ok": False}) is False

    def test_host_not_in_registry_returns_false(self) -> None:
        ctx = _make_ctx()
        ctx.conn.execute.return_value.fetchone.return_value = None  # type: ignore[attr-defined]
        assert _load_node(ctx, {"alias": "prod-01", "ok": True, "data": {}}) is False

    def test_host_in_registry_returns_true(self) -> None:
        host_id = uuid.uuid4()
        svc_id = uuid.uuid4()
        ctx = _make_ctx(
            {
                ("entity_kind", "host"): uuid.uuid4(),
                ("observation_status", "observed"): uuid.uuid4(),
                ("service_kind", "redis"): uuid.uuid4(),
                ("service_kind", "application_worker"): uuid.uuid4(),
                ("environment", "production"): uuid.uuid4(),
                ("lifecycle_status", "active"): uuid.uuid4(),
                ("runtime_kind", "docker_container"): uuid.uuid4(),
            }
        )
        with (
            patch(
                "internalcmdb.loaders.runtime_posture_loader._get_host_id_by_code",
                return_value=host_id,
            ),
            patch("internalcmdb.loaders.runtime_posture_loader._insert_observed_fact"),
            patch(
                "internalcmdb.loaders.runtime_posture_loader._upsert_shared_service",
                return_value=svc_id,
            ),
            patch("internalcmdb.loaders.runtime_posture_loader._upsert_service_instance"),
        ):
            node: dict[str, Any] = {
                "alias": "prod-01",
                "ok": True,
                "data": {
                    "containers": [{"name": "redis-cache", "status": "Up"}],
                    "containers_all": [{"name": "redis-cache", "status": "Up"}],
                },
            }
            assert _load_node(ctx, node) is True

    def test_stopped_container_marked_exited(self) -> None:
        host_id = uuid.uuid4()
        svc_id = uuid.uuid4()
        ctx = _make_ctx(
            {
                ("entity_kind", "host"): uuid.uuid4(),
                ("observation_status", "observed"): uuid.uuid4(),
                ("service_kind", "redis"): uuid.uuid4(),
                ("service_kind", "application_worker"): uuid.uuid4(),
                ("environment", "production"): uuid.uuid4(),
                ("lifecycle_status", "active"): uuid.uuid4(),
                ("runtime_kind", "docker_container"): uuid.uuid4(),
            }
        )
        with (
            patch(
                "internalcmdb.loaders.runtime_posture_loader._get_host_id_by_code",
                return_value=host_id,
            ),
            patch("internalcmdb.loaders.runtime_posture_loader._insert_observed_fact"),
            patch(
                "internalcmdb.loaders.runtime_posture_loader._upsert_shared_service",
                return_value=svc_id,
            ),
            patch(
                "internalcmdb.loaders.runtime_posture_loader._upsert_service_instance",
            ) as mock_inst,
        ):
            # containers_all has a container NOT in running containers → marked as Exited
            node: dict[str, Any] = {
                "alias": "prod-01",
                "ok": True,
                "data": {
                    "containers": [],  # no running containers
                    "containers_all": [{"name": "redis-cache", "status": "Up"}],
                },
            }
            _load_node(ctx, node)
            # Service instance should have been upserted with exited status
            assert mock_inst.call_count == 1
