---
id: CAP-001
title: internalCMDB — Capacity Growth and Cost Models (Wave-1)
doc_class: policy_pack
domain: platform-foundations
version: "1.0"
status: approved
created: 2026-03-08
updated: 2026-03-08
owner: platform_architecture_lead
tags: [capacity, cost, growth-model, wave-1, m13-1]
---

# internalCMDB — Capacity Growth and Cost Models

## 1. Purpose

Capacity and cost baseline covering storage growth, query load, and concurrency expectations.
Satisfies pt-040 [m13-1].

---

## 2. Storage Growth Model

### Database Tables

| Table | Estimated Row/Month | Row Size (avg) | Monthly Growth |
|---|---|---|---|
| observed_fact | 5,000 | 2 KB | ~10 MB |
| chunk_embedding | 20,000 | 4 KB (content) + 6 KB (vector) | ~200 MB |
| agent_run | 500 | 1 KB | ~0.5 MB |
| evidence_pack | 200 | 3 KB | ~0.6 MB |
| action_request | 100 | 2 KB | ~0.2 MB |
| prompt_template_registry | 20 | 4 KB | ~0.08 MB |
| document_version | 50 | 10 KB | ~0.5 MB |

**Total DB growth**: ~212 MB/month in Wave-1 operational mode.

**12-month projection**: ~2.5 GB — well within single NVMe capacity (1.92 TB).

### Vector Index (pgvector)

IVFFlat index rebuild recommended at 100k+ vectors (approx. 5 months at current rate).

---

## 3. Query Load Model

| Query Surface | Expected QPS (Wave-1) | P95 Latency Target |
|---|---|---|
| ServiceInstance discovery | 10 | 50ms |
| ObservedFact ingestion | 5 | 30ms |
| Chunk retrieval (ANN search) | 8 | 200ms |
| Agent run create/update | 3 | 50ms |
| Policy enforcement (enforcement_context) | 8 | 20ms |
| Approval workflow | 1 | 100ms |

**Peak concurrent connections**: 20 (well within PostgreSQL default max_connections=100).

---

## 4. Concurrency Expectations

| Component | Max Concurrent Instances | Notes |
|---|---|---|
| internalcmdb-app (API workers) | 4 | Uvicorn worker count |
| vLLM reasoning_32b | 4 concurrent requests | vLLM --max-num-seqs |
| vLLM fast_9b | 8 concurrent requests | vLLM --max-num-seqs |
| PostgreSQL connections | 20 | SQLAlchemy pool_size=5 per worker × 4 workers |

---

## 5. Cost Baseline (Wave-1, Self-Hosted Hetzner)

| Resource | Monthly Cost (EUR) | Notes |
|---|---|---|
| Hetzner ax101 bare-metal | ~210 | Includes 256 GB RAM, RTX 6000 Ada, 2×1.92TB NVMe |
| Electricity (GPU inference) | ~30 | Estimated 150W average GPU load |
| Backup storage | ~5 | Hetzner Storage Box 500 GB |
| **Total** | **~245 EUR/month** | |

**Cost per agent run** (at 500 runs/month): ~0.49 EUR per run (compute only).

---

## 6. Scale Triggers

| Metric | Trigger Threshold | Action |
|---|---|---|
| DB size > 80% of allocation | > 1.5 TB | Add storage or archive old facts |
| Connection pool exhaustion | pool wait > 50ms sustained | Increase pool_size or add read replica |
| Query latency degradation | P95 > 2× target | VACUUM ANALYZE + index review |
| Vector index ANN recall degradation | recall < 0.85 | Rebuild IVFFlat index |
| GPU VRAM exhaustion | > 90% utilization | Restrict concurrent requests; alert ALT-007 |

---

## 7. Verification

- [x] Growth estimates cover all major registry tables.
- [x] 12-month storage projection is within hardware capacity.
- [x] Query load model covers all critical surfaces.
- [x] Concurrency expectations are explicit.
- [x] Cost baseline and scale triggers are documented.
