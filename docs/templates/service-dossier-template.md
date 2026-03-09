---
id: SVC-NNN           # REQUIRED — next available SVC number e.g. SVC-001
title: "<Service name> — Service Dossier"  # REQUIRED
doc_class: service_dossier  # REQUIRED — do not change
domain: infrastructure  # REQUIRED — change to service's domain
version: "1.0"        # REQUIRED — quoted decimal
status: draft         # REQUIRED
created: "2026-03-09"   # REQUIRED
updated: "2026-03-09"   # REQUIRED
owner: platform_engineering_lead  # REQUIRED — role token of the service owner
binding:
  - entity_type: registry.services  # REQUIRED for service dossiers — do not change schema.table
    entity_id: "<service_name>"      # REQUIRED — replace with canonical service name
    relation: describes
tags: []
depends_on: []
---

# SVC-NNN: <Service Name> — Service Dossier

<!-- Replace SVC-NNN and Service Name. Remove this comment. -->

## Service Identity

| Field | Value |
| --- | --- |
| **Service name** | <!-- Canonical name matching registry.services.service_name --> |
| **Service type** | <!-- e.g. database, cache, message-broker, api, proxy, monitoring --> |
| **Registry entity** | `[[entity:registry.services:<service_name>]]` |
| **Host(s)** | `[[entity:registry.hosts:<hostname>]]` |
| **Criticality** | <!-- critical / high / medium / low --> |
| **Owner role** | <!-- canonical role token --> |

## Purpose and Function

<!-- 1-2 paragraphs: what does this service do, why does it exist,
what depends on it being available? -->

## Runtime Environment

| Field | Value |
| --- | --- |
| **Deployment model** | <!-- container / systemd / bare-metal / managed --> |
| **Container image** | <!-- repo/image:tag or N/A --> |
| **Runtime host** | <!-- hostname or cluster --> |
| **Port(s)** | <!-- e.g. 5432/tcp (PostgreSQL) --> |
| **Network segment** | <!-- e.g. vSwitch 10.10.0.0/24 --> |
| **Data directory** | <!-- e.g. /mnt/HC_Volume_105014654/docker/postgres --> |

## Configuration

<!-- Key configuration references. Do NOT include secrets or credentials here.
Reference the secrets policy for how credentials are managed. -->

| Parameter | Location | Description |
| --- | --- | --- |
| <!-- param --> | <!-- file/env/vault path --> | <!-- what it controls --> |

**Secrets management:** per [[doc:POL-002]] — no credentials stored in this document.

## Dependencies

### Upstream dependencies (what this service needs)

| Dependency | Type | Required |
| --- | --- | --- |
| <!-- service/resource --> | <!-- service/infra/network --> | <!-- yes/no --> |

### Downstream consumers (what depends on this service)

| Consumer | Dependency type |
| --- | --- |
| <!-- service/component --> | <!-- reads/writes/queries --> |

## Operational Characteristics

| Metric | Value | Source |
| --- | --- | --- |
| **RTO** | <!-- e.g. 4h --> | [[doc:POL-001]] |
| **RPO** | <!-- e.g. 1h --> | [[doc:POL-001]] |
| **Backup schedule** | <!-- e.g. daily at 02:00 UTC --> | |
| **Health check** | <!-- e.g. TCP:5432 every 30s --> | |
| **Alert threshold** | <!-- e.g. down > 5min → page --> | |

## State and Provenance

| Field | Value |
| --- | --- |
| **Canonical state source** | <!-- registry.services or git --> |
| **Observed via** | <!-- discovery loader / manual audit --> |
| **Last observed** | <!-- YYYY-MM-DD or link to discovery run --> |
| **Drift policy** | <!-- tolerated / triggers reconciliation --> |

## Runbooks

<!-- List operational runbooks that apply to this service. -->

| Procedure | Runbook |
| --- | --- |
| <!-- procedure name --> | [[doc:RUN-NNN]] |

## Change History

| Version | Date | Changed by | Summary |
| --- | --- | --- | --- |
| 1.0 | <!-- YYYY-MM-DD --> | <!-- role token --> | Initial dossier |
