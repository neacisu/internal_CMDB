---
id: OBS-005
title: internalCMDB — Instrumentation and Export Contracts (Prometheus, Loki) (Wave-1)
doc_class: policy_pack
domain: observability
version: "1.0"
status: approved
created: 2026-03-08
updated: 2026-03-08
owner: platform_architecture_lead
tags: [instrumentation, prometheus, loki, export, wave-1, m7-4]
depends_on: [OBS-004]
---

# internalCMDB — Instrumentation and Export Contracts

## 1. Purpose

Instrumentation contract describing how signals are emitted, collected, labeled, retained, and queried.
Satisfies pt-047 [m7-4].

---

## 2. Prometheus Export Contract

### Application Metrics

The `internalcmdb-api` service exposes metrics on `:4444/metrics`.

| Label | Required | Description |
| --- | --- | --- |
| `service` | YES | Always `internalcmdb` |
| `env` | YES | `wave1-production` |
| `component` | YES | `registry`, `retrieval`, `control`, `broker` |
| `task_type` | Where applicable | Task type code for per-task metrics |

### Scrape Configuration (Prometheus)

```yaml
scrape_configs:
  - job_name: internalcmdb-api
    static_configs:
      - targets: ["internalcmdb-api:4444"]
    scrape_interval: 15s
    labels:
      env: wave1-production

  - job_name: postgres
    static_configs:
      - targets: ["postgres-exporter:9187"]
    scrape_interval: 30s

  - job_name: node
    static_configs:
      - targets: ["node-exporter:9100"]
    scrape_interval: 30s

  - job_name: nvidia-gpu
    static_configs:
      - targets: ["dcgm-exporter:9400"]
    scrape_interval: 15s
```

---

## 3. Loki Log Export Contract

All container logs exported via Promtail / Docker Loki driver.

| Label | Required | Description |
| --- | --- | --- |
| `container` | YES | Docker container name |
| `env` | YES | `wave1-production` |
| `service` | YES | Service identifier |

Log format requirement: structured JSON where possible. Unstructured logs must include timestamp and severity.

### Retention

| Log Class | Retention | Deletion Policy |
| --- | --- | --- |
| Application logs | 30 days | Auto-expire in Loki |
| PostgreSQL slow query | 14 days | Auto-expire |
| vLLM access logs | 30 days | Auto-expire |
| SSH auth logs | 90 days | Manual review; per OBS-002 |

---

## 4. Metric Naming Convention

```
internalcmdb_<component>_<measurement>[_<unit>][_total]
```

Examples:
- `internalcmdb_retrieval_latency_seconds` — histogram
- `internalcmdb_agent_run_total` — counter
- `internalcmdb_policy_denial_total` — counter
- `internalcmdb_approval_pending_total` — gauge

---

## 5. Verification

- [x] Signal collection paths are explicit.
- [x] Prometheus scrape configuration is complete.
- [x] Loki log labels and retention are defined.
- [x] Metric naming convention follows documented standard.
- [x] Sufficient to support dashboards, alerts, and investigations.
