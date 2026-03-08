---
id: ADR-002
title: System of Record — PostgreSQL as the Authoritative Operational Registry
status: approved
date: 2026-03-08
created: 2026-03-08
updated: 2026-03-08
deciders:
  - name: Alex Neacsu
    role: Architecture Board
    approved_at: 2026-03-08
doc_class: adr
domain: platform-foundations
version: "1.0"
owner: platform_architecture_lead
binding: []
tags: [system-of-record, postgresql, registry, wave-1]
---

# ADR-002 — System of Record: PostgreSQL as Authoritative Operational Registry

## Status

**Accepted** — 2026-03-08, Alex Neacsu (Architecture Board)

---

## Context

The platform needs a queryable, relational, strongly-typed operational registry for entities,
relationships, provenance, lifecycle and observed facts. This registry must support structured
filtering, integrity constraints, audit trails and ownership tracking simultaneously.

Multiple alternatives were evaluated: MongoDB (document store), graph database (Neo4j-class),
plain filesystem, and PostgreSQL. The choice has long-term architectural consequences because it
shapes query contracts, retrieval patterns, migration discipline and agent context assembly.

---

## Decision

**PostgreSQL 17 is the authoritative system of record for all operational registry data.
No operational registry entity may exist exclusively in another system without a corresponding
record in PostgreSQL backed by provenance and lifecycle fields.**

### Technology stack bindings

| Component | Choice | Rationale |
|---|---|---|
| Relational core | PostgreSQL 17 | ACID, RLS, FKs, rich types, proven at scale |
| Flexible metadata | JSONB columns | Schema-flexible extension without EAV anti-pattern |
| Vector storage | pgvector extension | Co-located with structured data, no separate vector DB needed |
| Full-text search | PostgreSQL FTS (`tsvector`, `tsquery`) | Lexical retrieval in deterministic-first pipeline without external index |
| Migration management | Alembic (Python) | Version-controlled, repeatable, downgrade-capable |
| ORM / query layer | SQLAlchemy 2.x (Core + ORM) | Typed, testable, compatible with strict mypy |
| Runtime packaging | Docker Compose on orchestrator | Isolated, bind-mounted, reproducible |

### Schema organization

Seven PostgreSQL schemas separate concerns:

| Schema | Purpose |
|---|---|
| `registry` | Infrastructure entities: hosts, clusters, services, networks, storage |
| `discovery` | Collectors, collection runs, observed facts, evidence artifacts, reconciliation |
| `taxonomy` | Controlled vocabularies: domains and terms |
| `docs` | Canonical documents, versions, entity bindings |
| `governance` | Policies, approvals, change log, schema version (alembic) |
| `retrieval` | Document chunks, embeddings, evidence packs |
| `agent_control` | Agent runs, action requests, prompt templates, evidence bindings |

### Data modelling rules

1. **Entities with stable identity use UUID primary keys** generated at insert time.
2. **Every business entity includes**: `created_at`, `updated_at`, `source_id`/`collector_id`,
   `confidence` (0.0–1.0), `lifecycle_status` (active/deprecated/archived).
3. **JSONB is permitted for**: extensible metadata, raw payloads, per-entity flexible attributes.
4. **JSONB is forbidden as a replacement for**: structured, queryable, indexed entity attributes
   that belong in typed columns with constraints.
5. **Foreign key integrity** is enforced except across schema boundaries where soft references
   are explicitly documented.
6. **Row-level security (RLS)** must be enabled on every business table in `registry`,
   `discovery`, `docs` and `agent_control`.

---

## Alternatives Considered

### Alt A — MongoDB as primary store
Document-native, schema-flexible. **Rejected**: no relational integrity, no native FK enforcement,
poor support for complex join queries needed for dependency mapping and evidence packs. Weaker
migration discipline. Does not satisfy audit and provenance requirements.

### Alt B — Neo4j or similar graph database
Excellent for relationship traversal. **Rejected** as initial core: lacks strong typing, ACID
guarantees are weaker, operational complexity is higher, PostgreSQL with FK relationships is
sufficient for wave-1 use cases and can be augmented with a graph layer later if needed.

### Alt C — Plain filesystem (JSON/YAML files)
Zero infrastructure cost. **Rejected**: no querying, no integrity, no concurrent writes, no
provenance model, unusable at registry scale.

### Alt D — Separate databases per schema concern (microservice pattern)
Cleaner service isolation. **Rejected for wave-1**: adds cross-service join complexity, no foreign
key integrity across databases, impractical for a single-engineer deployment. Can be revisited
at scale.

---

## Consequences

### Positive
- All operational entities queryable with ACID guarantees and relational integrity.
- Single migration tool (Alembic) for the full schema.
- Evidence packs can join registry, discovery and document tables in single queries.
- pgvector co-location eliminates an entire service tier.

### Negative / Tradeoffs
- Schema migrations require careful versioning and downgrade path planning.
- PostgreSQL operational burden (backup, storage, tuning) concentrated on orchestrator.
- RLS adds query complexity that must be covered by integration tests.

---

## Implementation Bindings

| Constraint | Binding |
|---|---|
| PostgreSQL version | 17-alpine container, pinned image |
| Container name | `internalcmdb-postgres` |
| Database name | `internalCMDB` |
| Credential management | `docs/policy-secrets-and-credentials.md` |
| Storage | Bind-mounted persistent volume on orchestrator |
| Migration baseline | `src/internalcmdb/migrations/versions/0001_wave1_initial_schema.py` |
| External access | Traefik TCP SNI on `postgres.orchestrator.neanelu.ro:5432` (ALPN postgresql) |

---

*Source: blueprint_platforma_interna.md §8.1, §9.2, ADR review 2026-03-08*
