# internalCMDB — Ownership Matrix & RACI

**Version**: 1.0
**Date**: 2026-03-08
**Approved by**: Alex Neacsu (Executive Sponsor, Architecture Board)

---

## Program Role Assignments

All platform roles are currently held by a single operator. This is explicitly accepted as the Wave-1
single-engineer posture and must be revisited before any external operator is granted write access.

| Program Role              | Named Owner  | Named At   | Purpose |
|---------------------------|--------------|------------|---------|
| Executive Sponsor         | Alex Neacsu  | 2026-03-08 | Resolves priorities, budget, cross-team escalations |
| Architecture Board        | Alex Neacsu  | 2026-03-08 | Approves canonical architectural decisions and exception paths |
| Platform Program Manager  | Alex Neacsu  | 2026-03-08 | Sequencing, governance, dependency tracking, status reporting |
| Platform Architecture Lead| Alex Neacsu  | 2026-03-08 | Target architecture coherence, schema boundaries, integration rules |
| Platform Engineering Lead | Alex Neacsu  | 2026-03-08 | Implementation ownership: registry, retrieval, brokers, runtime packaging |
| Data Registry Owner       | Alex Neacsu  | 2026-03-08 | Registry data model, provenance model, migrations, seed quality |
| Discovery Owner           | Alex Neacsu  | 2026-03-08 | Collectors, normalization, confidence scoring, freshness guarantees |
| Security & Policy Owner   | Alex Neacsu  | 2026-03-08 | Approval model, policy engine, action restrictions, audit controls |
| SRE / Observability Owner | Alex Neacsu  | 2026-03-08 | Telemetry, alerting, retention, operational readiness |
| Domain Owners             | Alex Neacsu  | 2026-03-08 | Approve canonical facts for infra, shared services, and applications |

---

## RACI Matrix — Core Entities (Wave-1)

**R** = Responsible (does the work) | **A** = Accountable (sign-off) | **C** = Consulted | **I** = Informed

### Schema & Registry Layer

| Entity / Activity                        | Exec Sponsor | Arch Board | Eng Lead | Data Registry Owner | Discovery Owner | Sec & Policy |
|------------------------------------------|:---:|:---:|:---:|:---:|:---:|:---:|
| `registry.cluster`                       | A   | C   | R   | R   | I   | I   |
| `registry.host`                          | A   | C   | R   | R   | C   | I   |
| `registry.host_hardware_snapshot`        | I   | I   | R   | R   | R   | I   |
| `registry.gpu_device`                    | I   | I   | R   | R   | R   | I   |
| `registry.shared_service`               | A   | C   | R   | R   | C   | I   |
| `registry.service_instance`             | I   | C   | R   | R   | R   | I   |
| `registry.service_exposure`             | I   | C   | R   | R   | R   | C   |
| `registry.service_dependency`           | I   | C   | R   | A   | C   | I   |
| `registry.cluster_membership`           | I   | I   | R   | R   | R   | I   |
| `registry.dns_resolver_state`           | I   | I   | R   | R   | R   | I   |
| `registry.network_interface`            | I   | I   | R   | R   | R   | I   |
| `registry.firewall_rule_snapshot`       | I   | I   | R   | R   | R   | A   |

### Discovery Layer

| Entity / Activity                        | Exec Sponsor | Arch Board | Eng Lead | Data Registry Owner | Discovery Owner | Sec & Policy |
|------------------------------------------|:---:|:---:|:---:|:---:|:---:|:---:|
| `discovery.discovery_source`            | I   | C   | R   | A   | R   | I   |
| `discovery.collection_run`              | I   | I   | R   | C   | R   | I   |
| `discovery.observed_fact`               | I   | C   | R   | C   | R   | I   |
| `discovery.evidence_artifact`           | I   | I   | R   | C   | R   | I   |
| SSH full-audit loader                    | I   | I   | R   | A   | R   | I   |
| Runtime posture loader                   | I   | I   | R   | A   | R   | I   |
| Trust surface loader                     | I   | C   | R   | A   | R   | A   |

### Taxonomy Layer

| Entity / Activity                        | Exec Sponsor | Arch Board | Eng Lead | Data Registry Owner | Discovery Owner |
|------------------------------------------|:---:|:---:|:---:|:---:|:---:|
| `taxonomy.taxonomy_domain`              | I   | A   | R   | R   | I   |
| `taxonomy.taxonomy_term`                | I   | A   | R   | R   | C   |
| Taxonomy seed (22 domains, 251 terms)   | I   | A   | R   | R   | I   |

### Docs Layer

| Entity / Activity                        | Exec Sponsor | Arch Board | Eng Lead | Data Registry Owner |
|------------------------------------------|:---:|:---:|:---:|:---:|
| `docs.document`                         | A   | A   | R   | R   |
| `docs.document_version`                 | I   | I   | R   | R   |
| `docs.entity_doc_binding`               | I   | C   | R   | R   |

### Governance Layer

| Entity / Activity                        | Exec Sponsor | Arch Board | Sec & Policy | Eng Lead |
|------------------------------------------|:---:|:---:|:---:|:---:|
| `governance.alembic_version`            | I   | A   | I   | R   |
| Schema migration approval               | A   | C   | C   | R   |
| Policy document approval                | A   | A   | R   | C   |

### Retrieval Layer

| Entity / Activity                        | Arch Board | Eng Lead | Discovery Owner |
|------------------------------------------|:---:|:---:|:---:|
| `retrieval.evidence_pack`               | C   | R   | C   |
| `retrieval.evidence_pack_item`          | I   | R   | C   |
| `retrieval.retrieval_request`           | C   | R   | I   |

### Agent Control Layer

| Entity / Activity                        | Arch Board | Eng Lead | Sec & Policy |
|------------------------------------------|:---:|:---:|:---:|
| `agent_control.agent_session`           | C   | R   | A   |
| `agent_control.action_request`          | A   | R   | A   |
| `agent_control.action_approval`         | A   | R   | R   |
| `agent_control.agent_evidence`          | I   | R   | C   |

---

## Infrastructure Ownership

| Component                                   | Accountable  | Responsible  | Notes |
|---------------------------------------------|--------------|--------------|-------|
| PostgreSQL 17 (internalcmdb-postgres)       | Alex Neacsu  | Alex Neacsu  | HC_Volume_105014654, orchestrator |
| Traefik TCP routing (postgres.orchestrator) | Alex Neacsu  | Alex Neacsu  | SNI on :5432, ALPN postgresql, cert via Cloudflare |
| Alembic migration runs                      | Alex Neacsu  | Alex Neacsu  | Must have `POSTGRES_SSLMODE=require` |
| Audit loaders (ssh, runtime, trust_surface) | Alex Neacsu  | Alex Neacsu  | Run from local Mac, connect via Traefik |
| SSH cluster access                          | Alex Neacsu  | Alex Neacsu  | 9/12 hosts reachable as of 2026-03-08 |

---

## Change Control Rules

1. Any schema migration (`alembic upgrade`) must be run by the Data Registry Owner.
2. Any change to `taxonomy.taxonomy_term` requires Architecture Board approval before seed re-run.
3. Any change to the Traefik TCP routing for postgres requires SRE/Observability Owner sign-off.
4. Discovery loaders may be run at any time by the Discovery Owner without additional approval.
5. Policy documents in this `docs/` folder require Executive Sponsor approval before taking effect.

---

*Generated: 2026-03-08 | Evidence: collection_run_id=aa5c8b96-07cb-492c-b322-399e0574d738*
