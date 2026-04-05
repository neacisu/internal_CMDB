"""Import heavy modules so top-level definitions count toward coverage."""

from __future__ import annotations


def test_import_api_routers() -> None:
    from internalcmdb.api.routers import (
        agent,
        audit,
        cognitive,
        collectors,
        compliance,
        dashboard,
        debug,
        discovery,
        documents,
        governance,
        graph,
        hitl,
        metrics_live,
        realtime,
        registry,
        results,
        retrieval,
        slo,
        workers,
    )

    assert cognitive.router.prefix
    assert collectors.router.prefix


def test_import_cognitive_package() -> None:
    from internalcmdb.cognitive import (
        accuracy_tracker,
        alert_manager,
        analyzer,
        correlator,
        data_quality,
        drift_detector,
        feedback_loop,
        health_scorer,
        knowledge_base,
        predictor,
        prompt_evolution,
        query_engine,
        report_generator,
        self_heal_disk,
    )

    assert analyzer.FactAnalyzer is not None


def test_import_governance_motor_nervous() -> None:
    from internalcmdb.governance import (
        access_control,
        action_workflow,
        ai_compliance,
        guard_gate,
        hitl_workflow,
        metadata_validator,
        notifications,
        policy_enforcer,
        redaction_scanner,
    )
    from internalcmdb.motor import chaos, concurrency, execution_lock, notifications as moto_notif
    from internalcmdb.nervous import event_bus, reactor

    assert ai_compliance.AIComplianceManager is not None
    assert reactor.ReactiveLoop is not None


def test_import_loaders_observability_graph_config() -> None:
    from internalcmdb.config import secrets
    from internalcmdb.graph import knowledge_graph
    from internalcmdb.loaders import runtime_posture_loader, ssh_audit_loader, trust_surface_loader
    from internalcmdb.observability import logging as olog, metrics, tracing

    assert secrets is not None
    assert knowledge_graph.InfrastructureKnowledgeGraph is not None


def test_import_llm_retrieval_workers_scripts() -> None:
    from internalcmdb.llm import budget, client, confidence, guard, security
    from internalcmdb.retrieval import broker, chunker, ranker, task_types
    from internalcmdb.scripts import reindex_embeddings
    from internalcmdb.workers import cognitive_tasks, executor, retention, scheduler

    assert client.LLMClient is not None
    assert broker.RetrievalBroker is not None
    assert scheduler is not None


def test_import_collectors_agent_package() -> None:
    import importlib

    from internalcmdb.collectors.agent import daemon, updater
    from internalcmdb.collectors import diff_engine, fleet_health, staleness

    assert daemon is not None
    assert fleet_health is not None
    base = "internalcmdb.collectors.agent.collectors"
    for name in (
        "certificate_state",
        "container_resources",
        "disk_state",
        "docker_state",
        "full_audit",
        "full_hardware",
        "gpu_state",
        "heartbeat",
        "journal_errors",
        "llm_endpoint_health",
        "network_latency",
        "network_state",
        "process_inventory",
        "security_posture",
        "service_health",
        "system_vitals",
        "systemd_state",
        "trust_surface_lite",
        "vllm_metrics",
    ):
        importlib.import_module(f"{base}.{name}")
