"""Shared service seed — idempotent upsert of all known shared services.

v1.5 — 2026-03-24 — wapp-pro-app dual-homed:
    eth0 10.0.1.105 (VLAN 4000) + eth1 95.216.36.226 (public, MAC 00:50:56:01:1F:F0).

v1.4 — 2026-03-24 — WAPP Pro: LXC wapp-pro-app host bootstrap, app services, proxy mesh metadata.

v1.3 — 2026-03-15 — host_hint: public IP + SSH alias for all services.

v1.2 — 2026-03-14 — Add 4 discovered services (activepieces, kafka, n8n, neo4j).

v1.1 — 2026-03-14 — Complete metadata enrichment + model data corrections.

Sources (verified against running infrastructure 2026-03-14):
  - deploy/orchestrator/docker-compose.postgresql.yml  (PostgreSQL)
  - deploy/orchestrator/redis.yml                      (Redis TCP SNI via Traefik)
  - subprojects/ai-infrastructure/docker-compose.yml   (vLLM primary+secondary, Open WebUI)
  - subprojects/ai-infrastructure-embed/docker-compose.yml (Ollama embedding)
  - docs/llm/LLM-001-model-serving-registry-routing.md (model classes, routing)
  - docs/observability/OBS-001..OBS-013                (Prometheus, Grafana, Loki, Tempo, …)
  - Application codebase                               (InternalCMDB API/Worker/Frontend/Scheduler)
  - taxonomy_seed.py service_kind domain               (canonical kind codes)

Usage (from repo root, schemas migrated, taxonomy seeded):

    python -m internalcmdb.seeds.shared_service_seed

Fully idempotent — uses INSERT … ON CONFLICT DO UPDATE (upsert).
Re-running updates name, description, is_active, and metadata_jsonb for
every service whose service_code already exists.
"""

from __future__ import annotations

import json
import os
import uuid
from collections.abc import Callable
from typing import Any, cast

import sqlalchemy as sa
from dotenv import load_dotenv
from sqlalchemy.dialects.postgresql import insert as pg_insert

# ---------------------------------------------------------------------------
# Service catalogue — v1.3
# Each tuple: (service_code, name, service_kind_code, environment_code,
#              lifecycle_code, description, metadata)
# ---------------------------------------------------------------------------

# category values used in metadata: "database" | "cache" | "proxy" |
#   "observability" | "security" | "ai_ml" | "application"

_HOST_ORCHESTRATOR = "77.42.76.185 (orchestrator)"
_HOST_HZ_113 = "49.13.97.113 (hz.113)"
_HOST_WAPP_PRO_APP = "10.0.1.105 / 95.216.36.226 (lxc-wapp-pro-app)"

_SERVICES: list[tuple[str, str, str, str, str, str | None, dict[str, Any]]] = [
    # ── Database ──────────────────────────────────────────────────────────────
    (
        "internalcmdb-postgres",
        "InternalCMDB PostgreSQL",
        "postgresql",
        "shared-platform",
        "active",
        "PostgreSQL 17 instance dedicated to internalCMDB. "
        "Bound on 127.0.0.1:5433; external access via Traefik TCP SNI. "
        "Volume on HC_Volume_105014654 (Hetzner Cloud Block Storage). "
        "Health-checked every 10 s via pg_isready.",
        {
            "category": "database",
            "host_hint": _HOST_ORCHESTRATOR,
            "port_hint": 5433,
            "bind_address": "127.0.0.1",
            "container_name": "internalcmdb-postgres",
            "image": "postgres:17-alpine",
            "exposure": "traefik_tcp_sni",
            "restart_policy": "unless-stopped",
            "volumes": [
                "/mnt/HC_Volume_105014654/postgresql/internalcmdb/data:/var/lib/postgresql/data",
            ],
            "networks": ["internalcmdb_net"],
            "health_check": {
                "test": "pg_isready -U internalcmdb -d internalCMDB",
                "interval": "10s",
                "timeout": "5s",
                "retries": 5,
                "start_period": "15s",
            },
            "environment": {
                "PGDATA": "/var/lib/postgresql/data/pgdata",
            },
        },
    ),
    (
        "pgbouncer-main",
        "PgBouncer (Connection Pooler)",
        "pgbouncer",
        "shared-platform",
        "planned",
        "Connection pooler in front of PostgreSQL. "
        "Planned for Wave-2 to reduce connection overhead under load.",
        {
            "category": "database",
            "host_hint": _HOST_ORCHESTRATOR,
            "port_hint": 5432,
            "exposure": "loopback_only",
        },
    ),
    # ── Cache ─────────────────────────────────────────────────────────────────
    (
        "redis-shared",
        "Redis Shared",
        "redis",
        "shared-platform",
        "active",
        "Shared Redis 7 instance. Exposed externally via Traefik TCP SNI on "
        "redis.infraq.app:443 (TLS-terminated by Traefik, plain TCP to Redis). "
        "Bound on 10.0.0.2:6379 (Hetzner vSwitch). "
        "Used by InternalCMDB worker queue (ARQ) and application caching.",
        {
            "category": "cache",
            "host_hint": _HOST_ORCHESTRATOR,
            "port_hint": 6379,
            "bind_address": "10.0.0.2",
            "container_name": "redis-shared",
            "image": "redis:7-alpine",
            "external_hostname": "redis.infraq.app",
            "external_port": 443,
            "exposure": "traefik_tcp_sni",
            "restart_policy": "unless-stopped",
            "traefik_entrypoint": "websecure",
            "traefik_cert_resolver": "cloudflare",
            "doc_ref": "deploy/orchestrator/redis.yml",
        },
    ),
    # ── Proxy / Ingress ───────────────────────────────────────────────────────
    (
        "traefik-proxy",
        "Traefik Reverse Proxy",
        "traefik",
        "shared-platform",
        "active",
        "Traefik ingress proxy. Handles HTTPS termination on :443, TCP SNI "
        "routing for PostgreSQL and Redis, and dynamic config reloading from "
        "/etc/traefik/dynamic/. Runs in host network mode on the orchestrator. "
        "Cert resolver: Cloudflare DNS challenge (Let's Encrypt).",
        {
            "category": "proxy",
            "host_hint": _HOST_ORCHESTRATOR,
            "port_hint": 443,
            "container_name": "traefik",
            "image": "traefik:v3",
            "exposure": "direct_host_port",
            "restart_policy": "unless-stopped",
            "network_mode": "host",
            "volumes": [
                "/var/run/docker.sock:/var/run/docker.sock:ro",
                "/opt/traefik:/etc/traefik",
            ],
            "entrypoints": {
                "web": 80,
                "websecure": 443,
            },
            "tls_cert_resolver": "cloudflare",
            "dynamic_config_dir": "/etc/traefik/dynamic/",
        },
    ),
    # ── Observability ─────────────────────────────────────────────────────────
    (
        "prometheus-main",
        "Prometheus",
        "prometheus",
        "shared-platform",
        "active",
        "Prometheus metrics scraper. Scrapes node_exporter, cadvisor, "
        "postgres_exporter, pve_exporter, and application /metrics endpoints. "
        "Retention policy governed by OBS-002. Storage: local TSDB.",
        {
            "category": "observability",
            "host_hint": _HOST_ORCHESTRATOR,
            "port_hint": 9090,
            "bind_address": "127.0.0.1",
            "container_name": "prometheus",
            "image": "prom/prometheus:latest",
            "exposure": "loopback_only",
            "restart_policy": "unless-stopped",
            "volumes": [
                "/opt/prometheus/config:/etc/prometheus",
                "/opt/prometheus/data:/prometheus",
            ],
            "doc_ref": "OBS-001",
            "scrape_targets": [
                "node-exporter-orchestrator:9100",
                "cadvisor-orchestrator:8080",
                "postgres-exporter-internalcmdb:9187",
                "pve-exporter-main:9221",
                "internalcmdb-api:4444/metrics",
            ],
        },
    ),
    (
        "grafana-main",
        "Grafana",
        "grafana",
        "shared-platform",
        "active",
        "Grafana dashboards for platform KPIs and SLOs. "
        "Datasources: Prometheus (metrics), Loki (logs), Tempo (traces). "
        "Auth via OAuth2 Proxy → Zitadel OIDC. Dashboard pack: OBS-007.",
        {
            "category": "observability",
            "host_hint": _HOST_ORCHESTRATOR,
            "port_hint": 3000,
            "bind_address": "127.0.0.1",
            "container_name": "grafana",
            "image": "grafana/grafana:latest",
            "exposure": "traefik_https",
            "restart_policy": "unless-stopped",
            "volumes": [
                "/opt/grafana/data:/var/lib/grafana",
            ],
            "datasources": ["prometheus", "loki", "tempo"],
            "auth": "oauth2-proxy → zitadel OIDC",
            "doc_ref": "OBS-007",
        },
    ),
    (
        "loki-main",
        "Loki (Log Aggregation)",
        "loki",
        "shared-platform",
        "active",
        "Loki log aggregation. Collects Docker stdout logs via Promtail, "
        "PostgreSQL slow-query logs, vLLM access logs, and SSH auth logs. "
        "Retention policy in OBS-002. Query interface via Grafana.",
        {
            "category": "observability",
            "host_hint": _HOST_ORCHESTRATOR,
            "port_hint": 3100,
            "bind_address": "127.0.0.1",
            "container_name": "loki",
            "image": "grafana/loki:latest",
            "exposure": "loopback_only",
            "restart_policy": "unless-stopped",
            "volumes": [
                "/opt/loki/data:/loki",
            ],
            "log_sources": [
                "docker stdout (via promtail)",
                "postgresql slow-query",
                "vllm access logs",
                "ssh auth logs",
            ],
            "doc_ref": "OBS-002",
        },
    ),
    (
        "tempo-main",
        "Tempo (Distributed Tracing)",
        "tempo",
        "shared-platform",
        "active",
        "Grafana Tempo for distributed tracing. Receives traces via OTLP from "
        "the OpenTelemetry Collector. Queryable from Grafana. "
        "Storage: local filesystem.",
        {
            "category": "observability",
            "host_hint": _HOST_ORCHESTRATOR,
            "port_hint": 3200,
            "bind_address": "127.0.0.1",
            "container_name": "tempo",
            "image": "grafana/tempo:latest",
            "exposure": "loopback_only",
            "restart_policy": "unless-stopped",
            "receives_from": ["otel-collector-main"],
            "protocol": "OTLP gRPC",
        },
    ),
    (
        "otel-collector-main",
        "OpenTelemetry Collector",
        "otel_collector",
        "shared-platform",
        "active",
        "OpenTelemetry Collector gateway. Receives OTLP traces and metrics from "
        "the application and forwards to Tempo (traces) and Prometheus "
        "(metrics via remote_write). Ports: 4317 (gRPC), 4318 (HTTP).",
        {
            "category": "observability",
            "host_hint": _HOST_ORCHESTRATOR,
            "port_hint": 4317,
            "bind_address": "127.0.0.1",
            "container_name": "otel-collector",
            "image": "otel/opentelemetry-collector-contrib:latest",
            "exposure": "loopback_only",
            "restart_policy": "unless-stopped",
            "ports": {"grpc": 4317, "http": 4318},
            "exporters": ["tempo (traces)", "prometheus (metrics)"],
        },
    ),
    (
        "node-exporter-orchestrator",
        "Node Exporter (Orchestrator)",
        "node_exporter",
        "shared-platform",
        "active",
        "Prometheus node_exporter on the orchestrator host. Exposes "
        "CPU, memory, disk, and network metrics. Signal: SIG-M-010.",
        {
            "category": "observability",
            "host_hint": _HOST_ORCHESTRATOR,
            "port_hint": 9100,
            "bind_address": "127.0.0.1",
            "container_name": "node-exporter",
            "image": "prom/node-exporter:latest",
            "exposure": "loopback_only",
            "restart_policy": "unless-stopped",
            "signal_ref": "SIG-M-010",
            "metrics": ["cpu", "memory", "disk", "network", "filesystem"],
        },
    ),
    (
        "cadvisor-orchestrator",
        "cAdvisor (Orchestrator)",
        "cadvisor",
        "shared-platform",
        "active",
        "Google cAdvisor container metrics exporter on the orchestrator. "
        "Scraped by Prometheus for per-container CPU/memory/network usage. "
        "Read-only bind to Docker socket.",
        {
            "category": "observability",
            "host_hint": _HOST_ORCHESTRATOR,
            "port_hint": 8080,
            "bind_address": "127.0.0.1",
            "container_name": "cadvisor",
            "image": "gcr.io/cadvisor/cadvisor:latest",
            "exposure": "loopback_only",
            "restart_policy": "unless-stopped",
            "volumes": [
                "/var/run/docker.sock:/var/run/docker.sock:ro",
                "/sys:/sys:ro",
                "/var/lib/docker/:/var/lib/docker:ro",
            ],
            "metrics": ["container_cpu", "container_memory", "container_network"],
        },
    ),
    (
        "postgres-exporter-internalcmdb",
        "Postgres Exporter (InternalCMDB)",
        "postgres_exporter",
        "shared-platform",
        "active",
        "Prometheus postgres_exporter for the InternalCMDB database. "
        "Exposes pg_up (SIG-M-001), pg_stat_activity_count (SIG-M-002), "
        "and connection pool metrics. Connects to internalcmdb-postgres:5432.",
        {
            "category": "observability",
            "host_hint": _HOST_ORCHESTRATOR,
            "port_hint": 9187,
            "bind_address": "127.0.0.1",
            "container_name": "postgres-exporter",
            "image": "prometheuscommunity/postgres-exporter:latest",
            "exposure": "loopback_only",
            "restart_policy": "unless-stopped",
            "networks": ["internalcmdb_net"],
            "depends_on": ["internalcmdb-postgres"],
            "signal_refs": ["SIG-M-001", "SIG-M-002"],
        },
    ),
    (
        "pve-exporter-main",
        "PVE Exporter (Proxmox)",
        "pve_exporter",
        "shared-platform",
        "active",
        "Prometheus pve_exporter for Proxmox cluster metrics. "
        "Provides VM/LXC resource usage visible in Grafana. "
        "Connects to Proxmox API via token auth.",
        {
            "category": "observability",
            "host_hint": _HOST_ORCHESTRATOR,
            "port_hint": 9221,
            "bind_address": "127.0.0.1",
            "container_name": "pve-exporter",
            "image": "prompve/prometheus-pve-exporter:latest",
            "exposure": "loopback_only",
            "restart_policy": "unless-stopped",
            "metrics": ["pve_node", "pve_vm", "pve_lxc", "pve_storage"],
        },
    ),
    # ── Security / Identity ───────────────────────────────────────────────────
    (
        "openbao-main",
        "OpenBao (Secrets Management)",
        "openbao",
        "shared-platform",
        "active",
        "OpenBao (open-source Vault fork) for secrets management. "
        "Stores database credentials, API tokens, and TLS certificates. "
        "Unsealed via Shamir keys. Policy: policy-secrets-and-credentials.md.",
        {
            "category": "security",
            "host_hint": _HOST_ORCHESTRATOR,
            "port_hint": 8200,
            "bind_address": "127.0.0.1",
            "container_name": "openbao",
            "image": "openbao/openbao:latest",
            "exposure": "traefik_https",
            "restart_policy": "unless-stopped",
            "volumes": [
                "/opt/openbao/data:/vault/data",
                "/opt/openbao/config:/vault/config",
            ],
            "seal_type": "shamir",
            "secret_engines": ["kv-v2", "database", "pki"],
            "doc_ref": "policy-secrets-and-credentials",
        },
    ),
    (
        "zitadel-main",
        "Zitadel (IAM / OIDC)",
        "zitadel",
        "shared-platform",
        "active",
        "Zitadel identity and access management provider. "
        "Issues OIDC tokens for Grafana, Open WebUI, and application SSO. "
        "Integrates with OAuth2 Proxy for header injection. "
        "Self-hosted with CockroachDB-embedded storage.",
        {
            "category": "security",
            "host_hint": _HOST_ORCHESTRATOR,
            "port_hint": 8080,
            "container_name": "zitadel",
            "image": "ghcr.io/zitadel/zitadel:latest",
            "exposure": "traefik_https",
            "restart_policy": "unless-stopped",
            "external_hostname": "auth.infraq.app",
            "external_port": 443,
            "protocols": ["OIDC", "OAuth2", "SAML"],
            "clients": ["grafana-main", "open-webui-main", "oauth2-proxy-main", "internalcmdb-api"],
        },
    ),
    (
        "oauth2-proxy-main",
        "OAuth2 Proxy",
        "oauth2_proxy",
        "shared-platform",
        "active",
        "OAuth2 Proxy middleware in front of Grafana and internal tooling. "
        "Validates tokens from Zitadel and injects X-Auth-Request headers. "
        "Upstream: Grafana on port 3000.",
        {
            "category": "security",
            "host_hint": _HOST_ORCHESTRATOR,
            "port_hint": 4180,
            "bind_address": "127.0.0.1",
            "container_name": "oauth2-proxy",
            "image": "quay.io/oauth2-proxy/oauth2-proxy:latest",
            "exposure": "traefik_https",
            "restart_policy": "unless-stopped",
            "depends_on": ["zitadel-main"],
            "upstream": "http://grafana:3000",
            "injected_headers": ["X-Auth-Request-User", "X-Auth-Request-Email"],
        },
    ),
    # ── AI / ML ───────────────────────────────────────────────────────────────
    (
        "vllm-reasoning-32b",
        "vLLM — Reasoning 32B (QwQ-32B-AWQ)",
        "vllm",
        "shared-platform",
        "active",
        "vLLM serving the Qwen/QwQ-32B-AWQ reasoning model on host port 8001. "
        "VRAM utilization: 65% of RTX 6000 Ada (≈31 GB). Max context: 24 576 tokens. "
        "Quantization: AWQ. Tensor parallel: 1. Enforce eager mode enabled. "
        "Task types: complex_analysis, multi_step_reasoning. "
        "GPU node: 10.0.1.13 (Hetzner bare-metal, Intel Xeon Gold 5412U, RTX 6000 Ada 48 GB).",
        {
            "category": "ai_ml",
            "host_hint": _HOST_HZ_113,
            "port_hint": 8001,
            "bind_address": "10.0.1.13",
            "container_name": "vllm-qwq-32b",
            "image": "vllm/vllm-openai:latest",
            "model_id": "qwq-32b-awq-v1",
            "model_class": "reasoning_32b",
            "hf_repo": "Qwen/QwQ-32B-AWQ",
            "quantization": "awq",
            "tensor_parallel_size": 1,
            "vram_utilization": 0.65,
            "max_model_len": 24576,
            "enforce_eager": True,
            "task_types": ["complex_analysis", "multi_step_reasoning"],
            "exposure": "private_vlan_only",
            "restart_policy": "unless-stopped",
            "ipc": "host",
            "volumes": [
                "/ai-infrastructure/models:/root/.cache/huggingface",
            ],
            "gpu": {
                "runtime": "nvidia",
                "count": 1,
                "model": "RTX 6000 Ada",
                "vram_total_gb": 48,
            },
            "depends_on": [],
            "doc_ref": "LLM-001",
        },
    ),
    (
        "vllm-fast-14b",
        "vLLM — Fast 14B (Qwen2.5-14B-Instruct-AWQ)",
        "vllm",
        "shared-platform",
        "active",
        "vLLM serving the Qwen/Qwen2.5-14B-Instruct-AWQ fast response model on host port 8002. "
        "VRAM utilization: 28% of RTX 6000 Ada (≈13 GB). Max context: 12 288 tokens. "
        "Quantization: AWQ. Tensor parallel: 1. "
        "Task types: summarization, classification, extraction. "
        "Falls back to reasoning-32b if unavailable.",
        {
            "category": "ai_ml",
            "host_hint": _HOST_HZ_113,
            "port_hint": 8002,
            "bind_address": "10.0.1.13",
            "container_name": "vllm-qwen-14b",
            "image": "vllm/vllm-openai:latest",
            "model_id": "qwen25-14b-instruct-awq-v1",
            "model_class": "fast_14b",
            "hf_repo": "Qwen/Qwen2.5-14B-Instruct-AWQ",
            "quantization": "awq",
            "tensor_parallel_size": 1,
            "vram_utilization": 0.28,
            "max_model_len": 12288,
            "task_types": ["summarization", "classification", "extraction"],
            "fallback_to": "vllm-reasoning-32b",
            "exposure": "private_vlan_only",
            "restart_policy": "unless-stopped",
            "ipc": "host",
            "volumes": [
                "/ai-infrastructure/models:/root/.cache/huggingface",
            ],
            "gpu": {
                "runtime": "nvidia",
                "count": 1,
                "model": "RTX 6000 Ada",
                "vram_total_gb": 48,
            },
            "depends_on": ["vllm-reasoning-32b"],
            "doc_ref": "LLM-001",
        },
    ),
    (
        "ollama-embed",
        "Ollama — Embedding 8B (Qwen3-Embedding-8B-Q5_K_M)",
        "ollama",
        "shared-platform",
        "active",
        "Ollama serving Qwen3-Embedding-8B (Q5_K_M quantization, 5.1 GB VRAM, dim=4096). "
        "Host: hz.62 (10.0.1.62). GPU: NVIDIA GTX 1080 8 GB (CUDA 6.1 / Pascal). "
        "Endpoint: 10.0.1.62:8003 → HAProxy VIP 10.0.1.10:49003. "
        "OpenAI-compatible: POST /v1/embeddings. "
        "Health-checked every 30 s via ollama list.",
        {
            "category": "ai_ml",
            "host_hint": "95.216.66.62 (hz.62)",
            "port_hint": 8003,
            "bind_address": "10.0.1.62",
            "container_name": "ollama-embed",
            "image": "ollama/ollama:latest",
            "model_id": "qwen3-embedding-8b-q5km",
            "model_class": "embedding_8b",
            "hf_repo": "Qwen/Qwen3-Embedding-8B-GGUF",
            "quantization": "Q5_K_M",
            "vram_usage_gb": 5.1,
            "embedding_dim": 4096,
            "exposure": "private_vlan_only",
            "restart_policy": "unless-stopped",
            "ipc": "host",
            "volumes": [
                "/ai-infrastructure-embed/models:/root/.ollama",
            ],
            "gpu": {
                "runtime": "nvidia",
                "count": 1,
                "model": "GTX 1080",
                "vram_total_gb": 8,
                "compute_capability": "6.1",
                "driver": "nvidia-driver-550-server",
                "toolkit": "nvidia-container-toolkit 1.18.2",
            },
            "environment": {
                "OLLAMA_HOST": "0.0.0.0:11434",
                "OLLAMA_KEEP_ALIVE": "24h",
                "OLLAMA_NUM_PARALLEL": "2",
                "OLLAMA_MAX_LOADED_MODELS": "1",
            },
            "health_check": {
                "test": "ollama list",
                "interval": "30s",
                "timeout": "10s",
                "retries": 3,
                "start_period": "60s",
            },
            "haproxy_vip": "10.0.1.10:49003",
            "api_endpoint": "POST /v1/embeddings",
            "doc_ref": "subprojects/ai-infrastructure-embed/docker-compose.yml",
        },
    ),
    (
        "open-webui-main",
        "Open WebUI",
        "open_webui",
        "shared-platform",
        "active",
        "Open WebUI chat interface unified over both vLLM endpoints. "
        "Port 3000 on the AI node (10.0.1.13). "
        "Backend connects to vllm-primary:8000 and vllm-secondary:8000 as OpenAI endpoints. "
        "Auth via Zitadel OIDC. Internal port: 8080.",
        {
            "category": "ai_ml",
            "host_hint": _HOST_HZ_113,
            "port_hint": 3000,
            "bind_address": "10.0.1.13",
            "container_name": "open-webui",
            "image": "ghcr.io/open-webui/open-webui:main",
            "exposure": "traefik_https",
            "restart_policy": "unless-stopped",
            "internal_port": 8080,
            "volumes": [
                "/ai-infrastructure/webui:/app/backend/data",
            ],
            "environment": {
                "ENABLE_OLLAMA_API": "false",
                "OPENAI_API_BASE_URLS": "http://vllm-primary:8000/v1;http://vllm-secondary:8000/v1",
            },
            "depends_on": ["vllm-reasoning-32b", "vllm-fast-14b"],
        },
    ),
    # ── Application (InternalCMDB) ────────────────────────────────────────────
    (
        "internalcmdb-api",
        "InternalCMDB API",
        "application_api",
        "production",
        "active",
        "FastAPI application exposing /api/v1/* endpoints for the registry, "
        "discovery, retrieval, documents, workers, and governance layers. "
        "Deployed as a uvicorn process on the orchestrator LXC. "
        "Connects to PostgreSQL (port 5433) and Redis (ARQ queue).",
        {
            "category": "application",
            "host_hint": _HOST_ORCHESTRATOR,
            "port_hint": 4444,
            "bind_address": "127.0.0.1",
            "exposure": "traefik_https",
            "stack": "FastAPI + SQLAlchemy + PostgreSQL + Redis",
            "runtime": "uvicorn",
            "depends_on": ["internalcmdb-postgres", "redis-shared"],
            "health_check": {
                "test": "GET /health",
                "interval": "30s",
            },
        },
    ),
    (
        "internalcmdb-worker",
        "InternalCMDB Worker",
        "application_worker",
        "production",
        "active",
        "ARQ async worker process. Executes scheduled and on-demand jobs: "
        "SSH audit, runtime posture audit, trust surface audit, and "
        "custom scripts via the workers API. "
        "Communicates with the API via Redis job queue (ARQ).",
        {
            "category": "application",
            "host_hint": _HOST_ORCHESTRATOR,
            "exposure": "not_exposed",
            "stack": "ARQ + Redis + Python",
            "runtime": "arq worker",
            "depends_on": ["redis-shared", "internalcmdb-postgres"],
        },
    ),
    (
        "internalcmdb-frontend",
        "InternalCMDB Frontend",
        "web_frontend",
        "production",
        "active",
        "Next.js 15 (App Router) frontend for InternalCMDB. Renders the "
        "dashboard, hosts, GPU, workers, services, discovery, results, "
        "documents and settings pages. Proxies /api/v1 to the FastAPI backend. "
        "Dev: port 3333. Production: behind Traefik HTTPS.",
        {
            "category": "application",
            "host_hint": _HOST_ORCHESTRATOR,
            "port_hint": 3333,
            "bind_address": "127.0.0.1",
            "exposure": "traefik_https",
            "stack": "Next.js 15 + Tailwind CSS v4 + shadcn/ui + TanStack Query",
            "runtime": "node",
            "depends_on": ["internalcmdb-api"],
        },
    ),
    (
        "internalcmdb-scheduler",
        "InternalCMDB Job Scheduler",
        "job_scheduler",
        "production",
        "active",
        "Cron-based job scheduler built into the ARQ worker (WorkerSchedule table). "
        "Manages recurring tasks: SSH connectivity checks, full audits, posture scans. "
        "Configurable via the Workers > Scheduler UI.",
        {
            "category": "application",
            "host_hint": _HOST_ORCHESTRATOR,
            "exposure": "not_exposed",
            "stack": "ARQ cron + PostgreSQL worker.worker_schedule",
            "runtime": "arq cron",
            "depends_on": ["internalcmdb-worker"],
        },
    ),
    # ── Discovered Services (external projects) ──────────────────────────────
    (
        "activepieces",
        "Activepieces (Flowxify)",
        "activepieces",
        "production",
        "active",
        "Low-code automation platform for the Flowxify project. "
        "Single container running Activepieces v0.44.0.",
        {
            "category": "application",
            "project": "flowxify",
            "host_hint": "94.130.68.123 (hz.123)",
            "container_name": "flowxify-activepieces",
            "image": "activepieces/activepieces:0.44.0",
            "exposure": "reverse_proxy",
            "runtime": "node",
        },
    ),
    (
        "kafka",
        "Apache Kafka (GeniusERP)",
        "kafka",
        "production",
        "active",
        "Apache Kafka 4.1.0 event-streaming broker for the GeniusERP project. "
        "Complemented by a Kafka Exporter sidecar for Prometheus metrics.",
        {
            "category": "application",
            "project": "geniuserp",
            "host_hint": "135.181.183.164 (hz.164)",
            "container_name": "geniuserp-kafka",
            "image": "apache/kafka:4.1.0",
            "exposure": "internal",
            "sidecars": [
                {
                    "container_name": "geniuserp-kafka-metrics",
                    "image": "danielqsj/kafka-exporter:v1.7.0",
                    "role": "prometheus_exporter",
                },
            ],
            "health_check": {"test": "broker health", "status": "healthy"},
        },
    ),
    (
        "n8n",
        "n8n Workflow Automation (Flowxify)",
        "n8n",
        "production",
        "active",
        "n8n workflow automation platform for the Flowxify project. "
        "Runs a main node plus two dedicated worker containers for parallel execution.",
        {
            "category": "application",
            "project": "flowxify",
            "host_hint": "94.130.68.123 (hz.123)",
            "container_name": "flowxify-n8n-main",
            "image": "docker.n8n.io/n8nio/n8n:latest",
            "exposure": "reverse_proxy",
            "runtime": "node",
            "workers": [
                "flowxify-n8n-worker-1",
                "flowxify-n8n-worker-2",
            ],
            "replicas": 3,
        },
    ),
    (
        "neo4j",
        "Neo4j Graph Database (GeniusERP)",
        "neo4j",
        "production",
        "active",
        "Neo4j 5.23 Enterprise graph database for the GeniusERP project. "
        "Fronted by an Nginx reverse proxy for metrics and access control.",
        {
            "category": "database",
            "project": "geniuserp",
            "host_hint": "135.181.183.164 (hz.164)",
            "container_name": "geniuserp-neo4j",
            "image": "neo4j:5.23-enterprise",
            "exposure": "reverse_proxy",
            "sidecars": [
                {
                    "container_name": "geniuserp-neo4j-metrics",
                    "image": "nginx:1.27-alpine",
                    "role": "reverse_proxy",
                },
            ],
        },
    ),
    # ── WAPP Pro (LXC wapp-pro-app, hz.215 CT 105) ─────────────────────────────
    (
        "evo-wapp-core",
        "WAPP Evolution API Core",
        "application_api",
        "production",
        "active",
        "Evolution API v2.3.7 (Baileys) on wapp-pro-app. "
        "Ports: host 26000 → container 7780; HAProxy VIP 26012.",
        {
            "category": "application",
            "project": "wapp-pro",
            "host_hint": _HOST_WAPP_PRO_APP,
            "container_name": "evo-wapp-core",
            "image": "evoapicloud/evolution-api:v2.3.7",
            "port_internal": 7780,
            "port_host": 26000,
            "haproxy_vip_port": 26012,
            "mem_limit": "6g",
        },
    ),
    (
        "evo-wapp-gateway",
        "WAPP Gateway (Fastify)",
        "application_api",
        "production",
        "active",
        "WAPP Gateway Fastify 5.x — API, webhooks, Socket.IO. "
        "Ports: host 26001 → 7781; HAProxy VIP 26010 (Traefik backend).",
        {
            "category": "application",
            "project": "wapp-pro",
            "host_hint": _HOST_WAPP_PRO_APP,
            "container_name": "evo-wapp-gateway",
            "image": "ghcr.io/alexneacsu/evo-wapp-gateway:latest",
            "port_internal": 7781,
            "port_host": 26001,
            "haproxy_vip_port": 26010,
            "mem_limit": "1g",
        },
    ),
    (
        "evo-wapp-workers",
        "WAPP Workers (BullMQ)",
        "application_worker",
        "production",
        "active",
        "BullMQ workers + health endpoint. "
        "Ports: host 26004 → 7784; HAProxy VIP 26013 (Prometheus scrape).",
        {
            "category": "application",
            "project": "wapp-pro",
            "host_hint": _HOST_WAPP_PRO_APP,
            "container_name": "evo-wapp-workers",
            "image": "ghcr.io/alexneacsu/evo-wapp-gateway:latest",
            "port_internal": 7784,
            "port_host": 26004,
            "haproxy_vip_port": 26013,
            "mem_limit": "1g",
        },
    ),
    (
        "wapp-admin",
        "WAPP Admin (Next.js)",
        "web_frontend",
        "production",
        "active",
        "Next.js 16 admin UI. Port host 26002 → 7782; HAProxy VIP 26011.",
        {
            "category": "application",
            "project": "wapp-pro",
            "host_hint": _HOST_WAPP_PRO_APP,
            "container_name": "wapp-admin",
            "image": "ghcr.io/alexneacsu/wapp-admin:latest",
            "port_internal": 7782,
            "port_host": 26002,
            "haproxy_vip_port": 26011,
            "mem_limit": "256m",
        },
    ),
]

# SOCKS5 proxy mesh -- metadata only (Etapa 2 deploy). One row per HAProxy VIP port 26100-26110.
_WAPP_PROXY_MESH_SPEC: list[tuple[str, str, str, str, str, str, str]] = [
    ("hz62", "hz.62", "26100", "10.0.1.62:1080", "95.216.66.62", "95.216.66.0/24", "T1"),
    ("hz113", "hz.113", "26101", "10.0.1.13:1080", "49.13.97.113", "49.13.97.0/24", "T1"),
    ("hz118", "hz.118", "26102", "10.0.1.4:1080", "95.216.72.118", "95.216.72.0/24", "T1"),
    ("hz123", "hz.123", "26103", "10.0.1.5:1080", "94.130.68.123", "94.130.68.0/24", "T1"),
    ("hz157", "hz.157", "26104", "10.0.1.3:1080", "95.216.225.157", "95.216.225.0/24", "T1"),
    ("hz164", "hz.164", "26105", "10.0.1.6:1080", "135.181.183.164", "135.181.183.0/24", "T1"),
    ("hz215", "hz.215", "26106", "10.0.1.9:1080", "95.216.36.215", "95.216.36.0/24", "T1"),
    ("hz223", "hz.223", "26107", "10.0.1.8:1080", "95.217.32.223", "95.217.32.0/24", "T1"),
    ("hz247", "hz.247", "26108", "10.0.1.7:1080", "95.216.68.247", "95.216.68.0/24", "T1"),
    (
        "orchestrator",
        "orchestrator",
        "26109",
        "10.0.1.18:1080",
        "77.42.76.185",
        "77.42.76.0/24",
        "T1",
    ),
    (
        "hz118spare",
        "hz.118-spare",
        "26110",
        "10.0.1.4:1081",
        "95.216.125.173",
        "95.216.125.0/24",
        "T2",
    ),
]

_SERVICES.extend(
    [
        (
            f"wapp-proxy-mesh-{suffix}",
            f"WAPP SOCKS mesh — {alias} (design Etapa 2)",
            "application_api",
            "production",
            "planned",
            f"Reserved SOCKS5 exit via HAProxy VIP :{haport} → microsocks {bind}. "
            f"Public exit {pub_ip} ({subnet}). Tier {tier}.",
            {
                "category": "proxy",
                "project": "wapp-pro",
                "design_only_etapa_2": True,
                "host_hint": f"{pub_ip} ({alias})",
                "haproxy_vip": "10.0.1.10",
                "haproxy_port": int(haport),
                "microsocks_bind": bind,
                "subnet_24": subnet,
                "tier": tier,
                "exit_public_ipv4": pub_ip,
            },
        )
        for suffix, alias, haport, bind, pub_ip, subnet, tier in _WAPP_PROXY_MESH_SPEC
    ]
)


def _upsert_wapp_pro_host(
    connection: sa.engine.Connection,
    get_term_id: Callable[[str], uuid.UUID],
) -> None:
    """Bootstrap registry.host for LXC wapp-pro-app (agent host_code lxc-wapp-pro-app)."""
    hid = uuid.uuid4()
    meta = {
        "parent_proxmox": "hz.215",
        "lxc_ctid": 105,
        "runtime_kind": "lxc_guest",
        "ssh_alias_mesh": "wapp-pro-app",
        "vlan": "4000",
        "network": {
            "eth0": {
                "ip": "10.0.1.105",
                "prefix": "/24",
                "gateway": "10.0.1.7",
                "mac": "BC:24:11:F1:D1:04",
                "bridge": "vmbr4000",
                "role": "internal_vlan4000",
            },
            "eth1": {
                "ip": "95.216.36.226",
                "prefix": "/32",
                "gateway": "95.216.36.193",
                "mac": "00:50:56:01:1F:F0",
                "bridge": "vmbr0",
                "role": "public_internet",
                "hetzner_dedicated_mac": True,
            },
        },
    }
    connection.execute(
        sa.text(
            """
            INSERT INTO registry.host (
              host_id, host_code, hostname, ssh_alias, fqdn,
              entity_kind_term_id, primary_host_role_term_id,
              environment_term_id, lifecycle_term_id, os_family_term_id,
              os_version_text, kernel_version_text, architecture_text,
              is_gpu_capable, is_docker_host, is_hypervisor,
              primary_public_ipv4, primary_private_ipv4,
              observed_hostname, confidence_score, metadata_jsonb
            ) VALUES (
              :id, :code, :hostname, :ssh_alias, NULL,
              :entity, :role, :env, :lifecycle, :os_fam,
              'Ubuntu LTS', NULL, 'amd64',
              FALSE, TRUE, FALSE,
              CAST(:pub_ip AS inet), CAST(:priv_ip AS inet),
              :hostname, 0.90, CAST(:meta AS jsonb)
            )
            ON CONFLICT (host_code) DO UPDATE SET
              hostname = EXCLUDED.hostname,
              ssh_alias = EXCLUDED.ssh_alias,
              primary_public_ipv4 = EXCLUDED.primary_public_ipv4,
              primary_private_ipv4 = EXCLUDED.primary_private_ipv4,
              primary_host_role_term_id = EXCLUDED.primary_host_role_term_id,
              lifecycle_term_id = EXCLUDED.lifecycle_term_id,
              is_docker_host = EXCLUDED.is_docker_host,
              metadata_jsonb = EXCLUDED.metadata_jsonb,
              updated_at = now()
            """
        ),
        {
            "id": hid,
            "code": "lxc-wapp-pro-app",
            "hostname": "wapp-pro-app",
            "ssh_alias": "wapp-pro-app",
            "entity": get_term_id("host"),
            "role": get_term_id("application_runtime_host"),
            "env": get_term_id("production"),
            "lifecycle": get_term_id("active"),
            "os_fam": get_term_id("ubuntu"),
            "pub_ip": "95.216.36.226",
            "priv_ip": "10.0.1.105",
            "meta": json.dumps(meta),
        },
    )


# ---------------------------------------------------------------------------
# Seeding logic — upsert (ON CONFLICT DO UPDATE)
# ---------------------------------------------------------------------------


def _build_url() -> str:
    load_dotenv()
    host = os.environ["POSTGRES_HOST"]
    port = os.environ.get("POSTGRES_PORT", "5432")
    db = os.environ["POSTGRES_DB"]
    user = os.environ["POSTGRES_USER"]
    password = os.environ["POSTGRES_PASSWORD"]
    return f"postgresql+psycopg://{user}:{password}@{host}:{port}/{db}"


def seed(connection: sa.engine.Connection) -> None:
    """Upsert all shared services — inserts new, updates existing."""
    term_table = sa.table(
        "taxonomy_term",
        sa.column("taxonomy_term_id"),
        sa.column("term_code"),
        schema="taxonomy",
    )

    def _get_term_id(code: str) -> uuid.UUID:
        row = connection.execute(
            sa.select(term_table.c.taxonomy_term_id).where(term_table.c.term_code == code)
        ).fetchone()
        if row is None:
            raise RuntimeError(f"Taxonomy term '{code}' not found — run taxonomy_seed first.")
        return cast(uuid.UUID, row[0])

    _upsert_wapp_pro_host(connection, _get_term_id)

    service_table = sa.table(
        "shared_service",
        sa.column("shared_service_id"),
        sa.column("service_code"),
        sa.column("name"),
        sa.column("service_kind_term_id"),
        sa.column("environment_term_id"),
        sa.column("lifecycle_term_id"),
        sa.column("is_active"),
        sa.column("description"),
        sa.column("metadata_jsonb"),
        schema="registry",
    )

    inserted = 0
    for (
        service_code,
        name,
        kind_code,
        env_code,
        lifecycle_code,
        description,
        metadata,
    ) in _SERVICES:
        kind_id = _get_term_id(kind_code)
        env_id = _get_term_id(env_code)
        lifecycle_id = _get_term_id(lifecycle_code)
        is_active = lifecycle_code == "active"

        stmt = pg_insert(service_table).values(
            shared_service_id=uuid.uuid4(),
            service_code=service_code,
            name=name,
            service_kind_term_id=kind_id,
            environment_term_id=env_id,
            lifecycle_term_id=lifecycle_id,
            is_active=is_active,
            description=description,
            metadata_jsonb=json.dumps(metadata),
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["service_code"],
            set_={
                "name": stmt.excluded.name,
                "service_kind_term_id": stmt.excluded.service_kind_term_id,
                "environment_term_id": stmt.excluded.environment_term_id,
                "lifecycle_term_id": stmt.excluded.lifecycle_term_id,
                "is_active": stmt.excluded.is_active,
                "description": stmt.excluded.description,
                "metadata_jsonb": stmt.excluded.metadata_jsonb,
            },
        )
        result = connection.execute(stmt)

        # pg_insert DO UPDATE always returns rowcount=1; detect insert vs update
        # by checking if xmax == 0 (insert) or xmax != 0 (update).  Simpler:
        # just count everything as "processed" and report totals.
        if result.rowcount and result.rowcount > 0:
            inserted += 1  # counts both inserts and updates

    connection.commit()
    total = len(_SERVICES)
    print(f"OK: {total} shared services processed, {inserted} upserted.")


def main() -> None:
    engine = sa.create_engine(_build_url())
    with engine.connect() as conn:
        seed(conn)
    engine.dispose()


if __name__ == "__main__":
    main()
