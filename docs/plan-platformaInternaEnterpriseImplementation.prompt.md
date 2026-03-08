---
name: planPlatformaInternaEnterpriseImplementation
description: Prompt de rafinare pentru planul enterprise al platformei interne, cu metadata structurata completa pastrata in corpul documentului.
id: PLAN-001
title: internalCMDB — Enterprise Implementation Plan (Wave-1 Baseline)
doc_class: policy_pack
domain: platform-foundations
version: "5.0"
status: approved
created: 2026-03-08
updated: 2026-03-08
owner: platform_program_manager
tags: [plan, wave-1, implementation, enterprise]
---

## Structured Plan Metadata

```yaml
plan_id: platforma-interna-enterprise-v5
plan_type: hybrid
status: wave-1-baseline-operational
planning_date: 2026-03-08
last_updated: 2026-03-08
source_blueprint: /Users/alexneacsu/Documents/ProiecteIT/docs/blueprint_platforma_interna.md
program_name: platforma-interna-enterprise-implementation
implementation_strategy: enterprise-first
coverage_status:
  blueprint_alignment: expanded-to-cover-registry-retrieval-control-plane-pilot-and-observability-foundations
  execution_track_alignment: effective-track-now-includes-broker-control-plane-pilot-artifacts-and-operational-readiness-work
  truthfulness_constraint: no-plan-may-claim-absolute-completeness-while-live-infrastructure-and-approval-decisions-can-still-refine-sequencing
  enterprise_completeness_position: materially-complete-for-wave-1-foundation-but-not-100-percent-complete-enterprise-wide
  known_remaining_enterprise_gap_areas:
    - supply-chain-security-and-software-integrity
    - environment-promotion-and-release-governance
    - capacity-cost-performance-and-resilience-engineering
    - llm-runtime-model-registry-and-evaluation-governance
    - data-governance-and-internal-compliance-controls
    - sustained-operation-proof
  addressed_gap_areas_wave1:
    - business-continuity-backup-restore-and-disaster-recovery  # docs/policy-rto-rpo.md — 2026-03-08
    - secrets-pki-and-trust-lifecycle-management               # docs/policy-secrets-and-credentials.md — 2026-03-08
    - named-raci-support-model-and-service-operations           # docs/ownership-matrix.md — 2026-03-08
validation_posture:
  planning_honesty_rule: treat-plan-as-enterprise-grade-and-materially-complete-for-wave-1-but-not-as-immutable-or-100-percent-final
  no-honest-reader-may-present-this-plan-as-100-percent-complete-or-100-percent-correct-in-absolute-enterprise-scope-before-live-validation-and-formal-approvals
  live_dependency_rule: infrastructure-facts-routing-policies-and-ownership-approvals-must-continue-to-be-revalidated-during-execution
  change_control_rule: all-later-adjustments-must-be-recorded-as-reviewed-plan-deltas-not-silent-edits
  anti_hallucination_rule: ai-voie-sa-afirmi-sa-proiectezi-sau-sa-implementezi-doar-ceea-ce-este-sustinut-de-artefacte-canonice-sau-date-observate-aprobate-orice-lipsa-de-evidenta-trebuie-escaladata-ca-gap-de-specificatie
  audit_first_rule: every-material-claim-or-change-must-start-from-canonical-evidence-or-approved-observed-data-not-from-assumption
planning_intent: >-
  Plan de implementare program-level pentru platforma interna enterprise de
  knowledge, registry operational, retrieval grounded, control plane pentru
  agenti si delivery orchestrat, derivat strict din blueprint-ul existent si din activele deja prezente in repo.
program_objectives:
  - operationalizarea unei surse canonice versionate pentru infrastructura, servicii si aplicatii
  - introducerea unui registry PostgreSQL-first pentru entitati, relatii, provenienta si stare
  - implementarea unui retrieval deterministic-plus-semantic evidence-first
  - eliminarea presupunerilor agentilor prin context broker, politici si approval gates
  - introducerea unui flux repetabil pentru delivery de aplicatii noi in infrastructura existenta
  - auditabilitate, reconciliere si observabilitate pentru toate schimbarile relevante
explicit_decisions:
  canonical_source: git-versioned-documents
  system_of_record: postgresql
  metadata_storage: jsonb
  vector_storage: pgvector
  lexical_search: postgresql-full-text-search
  embeddings_strategy: local-self-hosted
  orchestration_language: python
  context_access_model: policy-controlled-context-broker
  retrieval_execution_model: deterministic-first-retrieval-broker-with-semantic-augmentation-on-prefiltered-subsets
  action_execution_model: action-broker-mediated-writes-with-approval-enforcement
  agent_run_audit_model: every-material-agent-run-must-produce-run-records-and-evidence-bindings
  approval_model: every-write-requires-explicit-approval
  first_operational_instance: current-cluster
  target_shape: multi-cluster-multi-environment-ready
  truth_model:
    canonical_state: approved-documents-in-git
    observed_state: machine-collected-runtime-facts
    desired_state: policy-and-standard-target-state
    evidence_state: provenance-backed-artifacts
    working_state: bounded-run-context-for-agents
  conflict_model:
    canonical_vs_observed: expose-both-and-block-write-until-reconciled-or-approved-override
scope:
  included:
    - canonical-document-taxonomy-and-template-system
    - application-definition-packs-and-service-contracts
    - operational-registry-and-entity-relationship-model
    - discovery-ingestion-normalization-and-provenance
    - reconciliation-and-drift-detection
    - deterministic-and-semantic-retrieval
    - evidence-pack-generation-and-context-brokerage
    - policy-engine-action-broker-and-approval-workflow
    - delivery-control-foundation-for-ai-built-applications
    - observability-audit-retention-and-program-kpis
    - first-end-to-end-pilot-application-flow
  excluded:
    - full-general-purpose-ui-platform-in-wave-1
    - unrestricted-agent-execution
    - write-paths-that-bypass-approval
    - graph-database-as-initial-core-system
    - complete-ci-cd-transformation-beyond-platform-needs
non_negotiables:
  - no-agent-may-invent-missing-facts
  - no-agent-may-assert-design-or-implement-anything-not-backed-by-canonical-artifacts-or-approved-observed-data
  - every-lack-of-evidence-must-be-escalated-as-a-specification-gap
  - no-write-action-may-bypass-the-action-broker
  - no-context-pack-may-omit-provenance-for-critical-claims
  - no-retrieval-flow-may-start-from-semantic-search-without-structured-filtering-when-structured-data-exists
  - no-registry-record-may-overwrite-canonical-truth-with-observed-state-without-reconciliation-rules
  - every-material-output-must-be-traceable-to-canonical-or-observed-evidence
program_roles:
  executive_sponsor:
    purpose: resolves priorities budget and cross-team escalations
    assignment_rule: must-be-named-before-execution-start
    named_owner: "Alex Neacsu"
    named_at: "2026-03-08"
  architecture_board:
    purpose: approves canonical architectural decisions and exception paths
    assignment_rule: must-be-established-in-epic-0
    named_owner: "Alex Neacsu"
    named_at: "2026-03-08"
  platform_program_manager:
    purpose: sequencing governance dependency tracking and status reporting
    assignment_rule: must-be-named-before-sprint-1
    named_owner: "Alex Neacsu"
    named_at: "2026-03-08"
  platform_architecture_lead:
    purpose: target architecture coherence schema boundaries and integration rules
    assignment_rule: must-be-named-before-epic-1
    named_owner: "Alex Neacsu"
    named_at: "2026-03-08"
  platform_engineering_lead:
    purpose: implementation ownership for registry retrieval brokers and runtime packaging
    assignment_rule: must-be-named-before-epic-2
    named_owner: "Alex Neacsu"
    named_at: "2026-03-08"
  data_registry_owner:
    purpose: registry data model provenance model migrations and seed quality
    assignment_rule: must-be-named-before-registry-build
    named_owner: "Alex Neacsu"
    named_at: "2026-03-08"
  discovery_owner:
    purpose: collectors normalization confidence scoring and freshness guarantees
    assignment_rule: must-be-named-before-epic-3
    named_owner: "Alex Neacsu"
    named_at: "2026-03-08"
  security_and_policy_owner:
    purpose: approval model policy engine action restrictions and audit controls
    assignment_rule: must-be-named-before-epic-5
    named_owner: "Alex Neacsu"
    named_at: "2026-03-08"
  sre_observability_owner:
    purpose: telemetry alerting retention and operational readiness
    assignment_rule: must-be-named-before-epic-7
    named_owner: "Alex Neacsu"
    named_at: "2026-03-08"
  domain_owners:
    purpose: approve canonical facts for infra shared services and applications
    assignment_rule: must-be-declared-per-domain-before-that-domain-is-onboarded
    named_owner: "Alex Neacsu"
    named_at: "2026-03-08"
success_metrics:
  - canonical-document-coverage-rate
  - shared-service-contract-completeness
  - registry-binding-coverage
  - discovery-freshness-slo
  - drift-detection-precision
  - evidence-pack-completeness-rate
  - approval-turnaround-time
  - deployment-repeatability-rate
  - context-token-reduction-per-task
  - implementation-lead-time-for-new-application
architecture_layers:
  - id: layer-1
    name: canonical-sources-layer
    purpose: stores approved versioned human-readable truth and execution artifacts
  - id: layer-2
    name: operational-registry-layer
    purpose: stores entities relations provenance lifecycle and queryable operational facts
  - id: layer-3
    name: retrieval-layer
    purpose: produces bounded evidence-backed context packs for agents and humans
  - id: layer-4
    name: discovery-and-reconciliation-layer
    purpose: collects runtime state normalizes it and compares it against canonical targets
  - id: layer-5
    name: agent-control-plane
    purpose: mediates context action approvals and policy-constrained execution
  - id: layer-6
    name: observability-and-audit-layer
    purpose: measures system health policy compliance traceability and rollout quality
execution_principles:
  - stabilize-taxonomy-before-mass-document-authoring
  - stabilize-registry-schema-before-broad-ingestion
  - implement-structured-retrieval-before-semantic-expansion
  - block-write-automation-until-policy-engine-and-approval-chain-are-live
  - onboard-one-pilot-domain-end-to-end-before-scale-out
  - treat-the-current-cluster-as-reference-instance-not-final-boundary

relevant_existing_assets:
  - path: /Users/alexneacsu/Documents/ProiecteIT/docs/blueprint_platforma_interna.md
    reuse_for: source architecture intent target layers principles and scope boundaries
  - path: /Users/alexneacsu/Documents/ProiecteIT/subprojects/cluster-full-audit/audit_full.py
    reuse_for: discovery collector patterns runtime fact extraction and normalization vocabulary
  - path: /Users/alexneacsu/Documents/ProiecteIT/subprojects/ai-infrastructure/docker-compose.yml
    reuse_for: reference runtime packaging style for infrastructure services
  - path: /Users/alexneacsu/Documents/ProiecteIT/subprojects/ai-infrastructure/llm.yml
    reuse_for: AI infrastructure deployment conventions and service grouping
  - path: /Users/alexneacsu/Documents/ProiecteIT/src/proiecteit/__main__.py
    reuse_for: CLI entrypoint style for future platform commands
  - path: /Users/alexneacsu/Documents/ProiecteIT/src/proiecteit/health.py
    reuse_for: health-check conventions for new platform services
  - path: /Users/alexneacsu/Documents/ProiecteIT/tests/test_cli.py
    reuse_for: CLI test patterns
  - path: /Users/alexneacsu/Documents/ProiecteIT/tests/test_health.py
    reuse_for: health endpoint and behavior testing patterns
  - path: /Users/alexneacsu/Documents/ProiecteIT/pyproject.toml
    reuse_for: packaging linting typing and test standards
  - path: /Users/alexneacsu/Documents/ProiecteIT/README.md
    reuse_for: top-level project framing and operator documentation conventions

program_epics:
  - id: epic-0
    status: in-progress
    name: program-foundations-and-governance
    objective: establish decisions governance ownership and execution rules that all later work depends on
    priority: critical
    owners:
      executive_owner: executive_sponsor
      delivery_owner: platform_program_manager
      architecture_owner: platform_architecture_lead
      approvers:
        - architecture_board
        - executive_sponsor
    depends_on: []
    milestone_ids: [m0-1, m0-2]
    sprint_ids: [sprint-1]
    risks:
      - unresolved-core-decisions-create-rework-across-every-subsequent-epic
      - ownership-gaps-cause-implicit-decisions-and-unsafe-execution
      - ambiguous-approval-authority-delays-all-write-related-capabilities
    assumptions:
      - leadership-will-appoint-named-role-holders-before-execution-begins
      - blueprint-principles-remain-the-authoritative-architecture-basis
      - enterprise-first-approach-remains-preferred-over-mvp-first-decomposition
    entry_criteria:
      - blueprint-reviewed-end-to-end
      - repository-baseline-understood
      - program-sponsor-available
    exit_criteria:
      - core-adrs-approved
      - ownership-model-documented
      - escalation-and-exception-model-approved
      - roadmap-rules-frozen-for-wave-1
  - id: epic-1
    status: in-progress
    name: canonical-sources-and-document-governance
    objective: create the canonical document model metadata rules template packs and governance required for grounded execution
    priority: critical
    owners:
      executive_owner: platform_architecture_lead
      delivery_owner: platform_engineering_lead
      domain_owners:
        - domain_owners
      approvers:
        - architecture_board
        - platform_architecture_lead
    depends_on: [epic-0]
    milestone_ids: [m1-1, m1-2]
    sprint_ids: [sprint-1, sprint-2]
    risks:
      - weak-taxonomy-breaks-registry-binding-retrieval-and-change-traceability
      - oversized-template-packs-reduce-real-adoption-and-drive-shadow-docs
      - missing-metadata-fields-prevent-clean-provenance-and-filtering
    assumptions:
      - canonical-documents-will-remain-in-git-not-in-a-separate-document-system-of-record
      - each-domain-will-assign-reviewers-for-document-approval
      - document-authors-can-follow-structured-frontmatter-and-template-rules
    entry_criteria:
      - governance-model-approved
      - document-classes-prioritized
      - target-domains-for-wave-1-selected
    exit_criteria:
      - taxonomy-approved
      - metadata-schema-versioned
      - validation-rules-executable
      - canonical-template-pack-published-for-wave-1-domains
  - id: epic-2
    status: completed
    completed_at: 2026-03-08
    completion_evidence:
      - alembic-migration-0001-applied-to-live-postgresql-on-orchestrator
      - 38-tables-in-7-schemas-verified-2026-03-08
      - first-full-backfill-executed-9-hosts-79-service-instances
    name: operational-registry-and-data-model
    objective: implement the operational registry structure query contracts provenance model and schema constraints required for enterprise-grade execution
    priority: critical
    owners:
      executive_owner: platform_architecture_lead
      delivery_owner: data_registry_owner
      approvers:
        - architecture_board
        - platform_architecture_lead
        - data_registry_owner
    depends_on: [epic-0, epic-1]
    milestone_ids: [m2-1, m2-2, m2-3]
    sprint_ids: [sprint-2, sprint-3, sprint-4]
    risks:
      - under-modeled-registry-creates-hidden-procedural-logic-and-breaks-queryability
      - overuse-of-jsonb-erodes-governance-searchability-and-integrity-controls
      - weak-provenance-model-makes-reconciliation-and-audit-non-defensible
    assumptions:
      - postgresql-remains-the-authoritative-system-of-record-for-wave-1-operational-state
      - live-cluster-facts-already-validated-remain-representative-for-wave-1-schema-shaping
      - registry-must-support-current-instance-first-without-blocking-future-multi-cluster-extension
    entry_criteria:
      - epic-0-exit-criteria-satisfied
      - epic-1-taxonomy-and-metadata-rules-frozen-for-wave-1
      - wave-1-entity-scope-confirmed-from-blueprint-and-live-audit
    exit_criteria:
      - logical-registry-model-approved
      - physical-schema-and-migration-strategy-approved
      - provenance-and-state-separation-model-validated
      - query-contracts-defined-for-retrieval-reconciliation-and-audit
  - id: epic-3
    status: completed
    completed_at: 2026-03-08
    completion_evidence:
      - ssh-audit-loader-operational-9-hosts-loaded
      - runtime-posture-loader-operational-9-nodes-79-service-instances
      - trust-surface-loader-operational-9-hosts-9-evidence-artifacts
      - collection-run-provenance-captured-collection_run_ids-in-discovery.collection_run
      - first-full-backfill-timestamp-2026-03-08
    name: discovery-ingestion-and-reconciliation
    objective: implement repeatable evidence-backed collection normalization loading and reconciliation across the real infrastructure in scope
    priority: critical
    owners:
      executive_owner: platform_engineering_lead
      delivery_owner: discovery_owner
      approvers:
        - platform_engineering_lead
        - data_registry_owner
        - discovery_owner
    depends_on: [epic-0, epic-1, epic-2]
    milestone_ids: [m3-1, m3-2, m3-3]
    sprint_ids: [sprint-4, sprint-5, sprint-6]
    risks:
      - raw-audit-script-output-may-not-map-cleanly-to-enterprise-registry-contracts
      - partial-or-stale-observations-can-be-mistaken-for-truth-without-provenance-controls
      - reconciliation-noise-can-hide-material-drift-and-owner-actionability
    assumptions:
      - existing-read-only-audit-assets-remain-the-correct-starting-point-for-wave-1-discovery
      - reachable-wave-1-machines-and-core-services-are-sufficient-to-establish-the-first-registry-baseline
      - collector-normalization-can-be-implemented-without-bypassing-the-approved-schema-contracts
    entry_criteria:
      - epic-2-core-schema-available-for-loader-design
      - source-priority-list-approved
      - normalization-rules-defined-for-wave-1-entities
    exit_criteria:
      - repeatable-loaders-operational-for-wave-1-sources
      - provenance-captured-for-all-ingested-observations
      - first-full-reconciliation-report-approved
      - freshness-and-drift-severity-rules-published
  - id: epic-4
    status: in-progress
    name: retrieval-and-evidence-brokerage
    objective: implement the bounded deterministic-first retrieval model and evidence-pack contracts used by agents and operators
    priority: critical
    owners:
      executive_owner: platform_architecture_lead
      delivery_owner: platform_engineering_lead
      approvers:
        - architecture_board
        - platform_architecture_lead
        - security_and_policy_owner
    depends_on: [epic-0, epic-1, epic-2, epic-3]
    milestone_ids: [m4-1, m4-2, m4-3]
    sprint_ids: [sprint-6, sprint-7, sprint-8]
    risks:
      - semantic-retrieval-can-overpower-structured-truth-if-ordering-is-not-enforced
      - oversized-context-packs-can-hide-gaps-and-reduce-auditability
      - missing-task-type-contracts-make-context-assembly-inconsistent-across-runs
    assumptions:
      - canonical-documents-registry-bindings-and-observed-facts-are-available-for-bounded-context-assembly
      - local-embedding-strategy-remains-approved-for-wave-1
      - supported-task-types-can-be-scoped-to-a-realistic-wave-1-set-before-broader-expansion
    entry_criteria:
      - retrieval-consumers-identified-from-real-wave-1-workflows
      - registry-query-contracts-available
      - canonical-document-versioning-and-binding-rules-stable
    exit_criteria:
      - task-type-catalog-approved
      - evidence-pack-contracts-approved
      - deterministic-first-retrieval-order-verified
      - bounded-context-quality-validated-on-real-wave-1-tasks
  - id: epic-5
    status: in-progress
    name: agent-control-plane-policy-and-approvals
    objective: establish the policy-controlled execution plane that mediates approvals actions prompt governance and auditable agent runs
    priority: critical
    owners:
      executive_owner: security_and_policy_owner
      delivery_owner: platform_engineering_lead
      approvers:
        - architecture_board
        - security_and_policy_owner
        - executive_sponsor
    depends_on: [epic-0, epic-2, epic-4]
    milestone_ids: [m5-1, m5-2, m5-3]
    sprint_ids: [sprint-7, sprint-8, sprint-9]
    risks:
      - uncontrolled-write-paths-would-break-the-core-safety-model-of-the-platform
      - incomplete-approval-models-would-create-unverifiable-human-bypass-behavior
      - weak-run-audit-would-make-post-incident-analysis-and-governance-insufficient
    assumptions:
      - read-only-analysis-and-write-actions-must-remain-clearly-separated-in-policy-and-tooling
      - approval-enforcement-must-bind-scope-intent-expiry-and-post-change-verification
      - prompt-templates-are-governed-artifacts-not-ephemeral-chat-operating-notes
    entry_criteria:
      - task-types-defined-by-epic-4
      - risk-classes-and-write-surfaces-identified
      - registry-and-audit-storage-can-store-run-and-approval-records
    exit_criteria:
      - policy-matrix-approved
      - mediated-action-contracts-enforced
      - run-audit-ledger-operational
      - deny-by-default-behavior-verified-for-unapproved-writes
  - id: epic-6
    status: in-progress
    name: delivery-control-and-pilot-application-flow
    objective: validate the full governed delivery model through a bounded real pilot using approved documents retrieval brokers approvals and verification artifacts
    priority: high
    owners:
      executive_owner: platform_program_manager
      delivery_owner: platform_engineering_lead
      domain_owners:
        - domain_owners
      approvers:
        - executive_sponsor
        - platform_program_manager
        - domain_owners
    depends_on: [epic-0, epic-1, epic-2, epic-3, epic-4, epic-5]
    milestone_ids: [m6-1, m6-2, m6-3]
    sprint_ids: [sprint-8, sprint-9, sprint-10]
    risks:
      - an-over-scoped-pilot-could-mix-too-many-unknowns-and-hide-platform-defects
      - manual-bypasses-could-falsely-signal-platform-readiness
      - incomplete-pilot-artifacts-would-break-traceability-and-repeatability
    assumptions:
      - a-bounded-wave-1-pilot-can-be-selected-from-real-current-platform-needs
      - the-first-pilot-must-prove-governed-repeatable-delivery-not-maximum-feature-complexity
      - all-mandatory-pilot-artifacts-remain-required-for-any-honest-validation-claim
    entry_criteria:
      - epic-5-control-plane-controls-available-for-pilot-execution
      - selected-pilot-scope-approved
      - required-shared-service-contracts-and-dependencies-documented
    exit_criteria:
      - pilot-artifact-pack-approved
      - first-governed-run-completed-with-full-audit
      - second-run-repeatability-verified
      - residual-manual-gaps-documented-as-platform-gaps-not-hidden-workarounds
  - id: epic-7
    status: in-progress
    name: observability-audit-retention-and-rollout
    objective: close the operational loop with metrics alerting retention runbooks readiness review and evidence-based rollout controls
    priority: high
    owners:
      executive_owner: sre_observability_owner
      delivery_owner: platform_program_manager
      approvers:
        - executive_sponsor
        - sre_observability_owner
        - security_and_policy_owner
    depends_on: [epic-0, epic-2, epic-3, epic-4, epic-5, epic-6]
    milestone_ids: [m7-1, m7-2, m7-3, m7-4, m7-5, m7-6]
    sprint_ids: [sprint-9, sprint-10, sprint-11, sprint-20, sprint-21, sprint-22]
    risks:
      - rollout-without-kpis-and-runbooks-would-create-non-defensible-operational-risk
      - weak-retention-rules-could-undermine-audit-or-create-unbounded-data-growth
      - readiness-reviews-without-gap-registers-would-encourage-optimistic-governance-failures
      - fragmented-observability-between-shared-platform-and-local-components-can-hide-material-failures
      - dashboards-without-alert-routing-and-tested-escalation-can-create-false-operability-confidence
    assumptions:
      - observability-must-cover-registry-discovery-retrieval-and-control-plane-surfaces-together
      - runbooks-are-required-for-any-alert-that-matters-operationally
      - readiness-to-scale-must-be-gated-by-evidence-not-narrative-confidence
      - shared-grafana-prometheus-loki-on-orchestrator-are-the-correct-operational-surface-for-visualization-and-alert-consumption
    entry_criteria:
      - pilot-run-evidence-available
      - control-plane-and-retrieval-surfaces-expose-reviewable-signals
      - audit-artifact-classes-and-retention-needs-identified
    exit_criteria:
      - kpi-and-slo-catalog-approved
      - dashboards-alerting-and-retention-active
      - runbooks-published-for-critical-flows
      - wave-2-readiness-review-recorded-with-explicit-go-or-hold-decision
      - shared-observability-signal-inventory-approved
      - alert-routing-and-escalation-paths-tested
      - retention-enforcement-and-runbook-linkage-verified-on-live-surfaces
  - id: epic-8
    status: in-progress
    name: business-continuity-backup-restore-and-disaster-recovery
    objective: define and validate business continuity backup restore and disaster recovery controls for internalCMDB and its critical operational artifacts
    priority: high
    owners:
      executive_owner: executive_sponsor
      delivery_owner: platform_program_manager
      approvers:
        - executive_sponsor
        - platform_engineering_lead
        - sre_observability_owner
    depends_on: [epic-2, epic-7]
    milestone_ids: [m8-1, m8-2, m8-3]
    sprint_ids: [sprint-12, sprint-13]
    risks:
      - backup-presence-without-restore-proof-creates-false-confidence
      - unclear-ha-posture-can-lead-to-implicit-and-unsafe-availability-expectations
      - disaster-response-without-tested-runbooks-increases-recovery-time-and-data-loss-risk
    assumptions:
      - internalcmdb-can-start-as-single-instance-only-if-that-posture-is-explicitly-accepted-and-tested
      - persistence-paths-and-export-locations-on-orchestrator-remain-available-for-backup-and-restore-design
      - business-continuity-controls-must-cover-both-database-state-and-critical-audit-evidence-surfaces
    entry_criteria:
      - epic-2-schema-and-runtime-baseline-available
      - epic-7-observability-and-runbook-foundations-available
      - backup-and-export-paths-documented
    exit_criteria:
      - rto-rpo-and-ha-posture-approved
      - restore-path-tested-and-documented
      - disaster-recovery-exercise-completed-with-findings-recorded
  - id: epic-9
    status: in-progress
    name: secrets-pki-and-trust-management
    objective: implement an enterprise-grade secrets certificate and trust lifecycle model for platform runtime and controlled access paths
    priority: high
    owners:
      executive_owner: security_and_policy_owner
      delivery_owner: platform_engineering_lead
      approvers:
        - security_and_policy_owner
        - architecture_board
        - executive_sponsor
    depends_on: [epic-5, epic-7]
    milestone_ids: [m9-1, m9-2, m9-3]
    sprint_ids: [sprint-13, sprint-14]
    risks:
      - bootstrap-credentials-may-persist-longer-than-allowed-without-a-secrets-program
      - certificate-lifecycle-gaps-can-break-trust-and-external-access-paths
      - unmanaged-privileged-credentials-undermine-the-control-plane-safety-model
    assumptions:
      - external-postgres-and-broker-paths-require-explicit-tls-and-trust-handling-not-implicit-host-trust
      - secret-rotation-must-align-with-role-bound-access-and-audit-controls
      - approved-secret-storage-must-support-current-runtime-constraints-on-orchestrator-and-associated-services
    entry_criteria:
      - write-path-and-approval-model-defined
      - externally-exposed-tls-reliant-services-identified
      - bootstrap-auth-exceptions-documented
    exit_criteria:
      - secrets-storage-and-access-boundaries-approved
      - bootstrap-secrets-rotated-or-decommissioned
      - certificate-lifecycle-and-trust-model-documented-and-tested
  - id: epic-10
    status: in-progress
    name: supply-chain-security-and-release-integrity
    objective: establish verifiable integrity controls for dependencies images packages and promoted artifacts used by the platform
    priority: high
    owners:
      executive_owner: security_and_policy_owner
      delivery_owner: platform_engineering_lead
      approvers:
        - security_and_policy_owner
        - platform_program_manager
        - platform_engineering_lead
    depends_on: [epic-1, epic-5]
    milestone_ids: [m10-1, m10-2, m10-3]
    sprint_ids: [sprint-14, sprint-15]
    risks:
      - untracked-third-party-dependencies-can-introduce-unknown-security-and-license-risk
      - unsigned-or-unscanned-images-weaken-runtime-trustworthiness
      - release-artifacts-without-provenance-cannot-be-defended-during-audit-or-incident-review
    assumptions:
      - python-and-container-based-components-need-a-common-integrity-and-attestation-model
      - release-integrity-controls-must-extend-to-broker-runtime-and-data-loading-toolchains
      - software-integrity-is-part-of-enterprise-completeness-not-an-optional-hardening-layer
    entry_criteria:
      - main-runtime-components-and-dependency-surfaces-identified
      - artifact-build-paths-documented
      - package-and-image-sources-approved-for-review
    exit_criteria:
      - sbom-and-scan-baseline-established
      - artifact-provenance-and-signing-policy-approved
      - release-integrity-reviewable-for-promoted-artifacts
  - id: epic-11
    status: in-progress
    name: environment-promotion-and-release-management
    objective: standardize promotion gates release approvals rollback contracts and deployment evidence chains across environments and release classes
    priority: medium
    owners:
      executive_owner: platform_program_manager
      delivery_owner: platform_engineering_lead
      approvers:
        - executive_sponsor
        - platform_program_manager
        - security_and_policy_owner
    depends_on: [epic-5, epic-7, epic-10]
    milestone_ids: [m11-1, m11-2, m11-3]
    sprint_ids: [sprint-15, sprint-16]
    risks:
      - changes-may-reach-production-without-consistent-governance-between-environments
      - rollback-without-drills-can-turn-routine-releases-into-incidents
      - missing-deployment-evidence-chains-break-auditability-of-release-decisions
    assumptions:
      - even-if-wave-1-does-not-require-full-ci-cd-transformation-it-still-needs-release-governance
      - migration-rollbacks-must-be-explicitly-modeled-for-database-bearing-changes
      - environment-classification-and-promotion-rules-must-match-the-actual-operating-model-not-a-generic-template
    entry_criteria:
      - supply-chain-integrity-baseline-available
      - policy-and-approval-model-available
      - deployment-classes-and-environment-scope-identified
    exit_criteria:
      - promotion-model-and-gates-approved
      - rollback-contracts-and-drills-documented
      - release-evidence-chain-operationalized
  - id: epic-12
    status: in-progress
    name: llm-runtime-model-registry-and-evaluation-governance
    objective: operationalize model serving model registry evaluation governance and safety controls for self-hosted agent-supporting runtimes
    priority: medium
    owners:
      executive_owner: platform_architecture_lead
      delivery_owner: platform_engineering_lead
      approvers:
        - architecture_board
        - platform_architecture_lead
        - security_and_policy_owner
    depends_on: [epic-4, epic-5, epic-10]
    milestone_ids: [m12-1, m12-2, m12-3]
    sprint_ids: [sprint-16, sprint-17]
    risks:
      - model-runtime-without-governance-can-undermine-agent-safety-and-cost-predictability
      - absent-evaluation-harness-makes-model-selection-subjective-and-non-repeatable
      - missing-fallback-rules-can-cause-broker-instability-under-load-or-failure
    assumptions:
      - self-hosted-model-usage-remains-part-of-the-platform-direction-for-bounded-agent-workflows
      - model-governance-must-be-tied-to-task-types-latency-constraints-and-policy-controls
      - runtime-selection-and-routing-cannot-be-left-as-implicit-operator-knowledge
    entry_criteria:
      - retrieval-and-control-plane-baselines-available
      - target-model-classes-and-use-cases-identified
      - infrastructure-capacity-context-available-from-current-ai-stack-observations
    exit_criteria:
      - model-serving-and-registry-baseline-approved
      - evaluation-harness-operational-on-supported-task-types
      - fallback-and-safety-controls-documented-and-tested
  - id: epic-13
    status: in-progress
    name: capacity-performance-and-resilience-engineering
    objective: define and validate capacity performance resilience and failure-behavior expectations for database brokers and supporting runtimes
    priority: medium
    owners:
      executive_owner: sre_observability_owner
      delivery_owner: platform_engineering_lead
      approvers:
        - sre_observability_owner
        - platform_program_manager
        - platform_architecture_lead
    depends_on: [epic-7, epic-8, epic-12]
    milestone_ids: [m13-1, m13-2, m13-3]
    sprint_ids: [sprint-17, sprint-18]
    risks:
      - growth-without-capacity-modeling-can-break-wave-2-rollout-confidence
      - untested-failure-behavior-can-cause-unsafe-fail-open-or-catastrophic-fail-closed-modes
      - latency-and-load-unknowns-can-undermine-broker-and-registry-usability
    assumptions:
      - postgres-vector-storage-and-broker-paths-need-explicit-load-and-latency-budgets
      - resilience-testing-must-use-realistic-failure-modes-observed-or-plausible-in-current-infrastructure
      - capacity-planning-must-cover-data-growth-and-query-patterns-not-only-host-cpu-and-ram
    entry_criteria:
      - observability-baseline-active
      - runtime-and-release-governance-baselines-available
      - critical-user-flows-and-load-surfaces-identified
    exit_criteria:
      - capacity-model-approved
      - load-and-stress-results-reviewed
      - failure-behavior-and-resilience-guards-documented
  - id: epic-14
    status: in-progress
    name: support-model-raci-finalization-and-service-operations
    objective: finalize named ownership support tiers recurring reviews and service operations discipline across the platform
    priority: medium
    owners:
      executive_owner: executive_sponsor
      delivery_owner: platform_program_manager
      approvers:
        - executive_sponsor
        - platform_program_manager
        - sre_observability_owner
    depends_on: [epic-0, epic-7, epic-11, epic-13]
    milestone_ids: [m14-1, m14-2, m14-3]
    sprint_ids: [sprint-18, sprint-19]
    risks:
      - abstract-roles-without-named-owners-prevent-accountability-during-incidents-and-audits
      - missing-support-tier-model-delays-response-and-escalation-during-failures
      - absent-review-cadence-causes-governance-drift-after-initial-wave-1-success
    assumptions:
      - mature-enterprise-operation-requires-human-operating-models-not-only-technical-controls
      - on-call-escalation-and-access-review-must-align-with-the-approved-risk-model
      - raci-finalization-must-happen-before-multi-domain-scale-out-is-claimed-operationally-ready
    entry_criteria:
      - core-platform-services-and-risk-classes-identified
      - observability-and-runbook-foundations-available
      - supplemental-enterprise-workstreams-sufficiently-defined-for-service-boundary-mapping
    exit_criteria:
      - named-raci-approved
      - support-and-on-call-model-operational
      - recurring-service-review-cadence-active
  - id: epic-15
    status: in-progress
    name: data-governance-and-internal-compliance-controls
    objective: classify all registry data by sensitivity apply ingest-time redaction controls for credentials and sensitive patterns model retention and deletion governance per data class and maintain a governed exception register with executive-approved compliance declaration
    priority: high
    owners:
      executive_owner: security_and_policy_owner
      delivery_owner: platform_engineering_lead
      approvers:
        - security_and_policy_owner
        - executive_sponsor
        - platform_program_manager
    depends_on: [epic-2, epic-5, epic-9]
    milestone_ids: [m15-1, m15-2, m15-3]
    sprint_ids: [sprint-23]
    risks:
      - unclassified-data-in-registry-can-expose-sensitive-infrastructure-facts-to-unauthorized-retrieval
      - absent-redaction-controls-allow-credentials-or-sensitive-patterns-to-be-stored-as-observed-facts
      - missing-retention-rules-create-operational-and-audit-risk-for-long-running-registries
      - undocumented-exceptions-to-classification-rules-erode-trust-in-the-compliance-posture
    assumptions:
      - wave-1-registry-contains-class-b-data-ip-addresses-accounts-key-fingerprints-requiring-access-control
      - no-class-c-credential-data-should-ever-reach-registry-tables-redaction-at-ingest-is-the-enforcement-point
      - compliance-framework-is-internal-policy-driven-for-wave-1-no-external-regulatory-obligation-unless-declared
    entry_criteria:
      - registry-schema-and-ingest-pipeline-defined
      - policy-engine-and-access-model-available
      - secrets-storage-model-approved-in-epic-9
    exit_criteria:
      - data-classification-matrix-approved
      - redaction-controls-operational-and-tested-at-ingest
      - retention-and-deletion-runbooks-documented-and-tested
      - data-governance-compliance-declaration-signed-by-executive-sponsor
  - id: epic-16
    status: in-progress
    name: sustained-operation-proof
    objective: demonstrate that all critical operational loops have been executed at least twice with results compared for regression and that the platform is demonstrably operated not only deployed through a formal sustained operation declaration approved by executive sponsor
    priority: high
    owners:
      executive_owner: executive_sponsor
      delivery_owner: platform_program_manager
      approvers:
        - executive_sponsor
        - sre_observability_owner
        - platform_program_manager
    depends_on: [epic-8, epic-9, epic-10, epic-11, epic-12, epic-13, epic-14, epic-15]
    milestone_ids: [m16-1, m16-2, m16-3]
    sprint_ids: [sprint-24]
    risks:
      - single-cycle-evidence-can-be-mistaken-for-operational-stability-without-proof-of-repeatability
      - runbooks-not-tested-by-non-authors-fail-under-real-incident-pressure
      - absent-sustained-operation-declaration-allows-wave-2-claims-without-operational-proof
      - regression-between-cycles-may-go-undetected-without-explicit-comparison-requirement
    assumptions:
      - second-cycle-execution-can-be-planned-within-natural-cadence-of-quarterly-reviews-and-annual-drills
      - sustained-operation-proof-is-a-program-gate-for-wave-2-not-an-optional-nice-to-have
      - some-second-cycle-evidence-can-come-from-epic-14-recurring-cadences-if-timing-aligns
    entry_criteria:
      - all-epics-8-through-15-have-completed-at-least-one-full-operational-cycle
      - recurring-review-cadences-from-epic-14-have-started
      - observability-and-runbook-foundations-active
    exit_criteria:
      - backup-restore-drill-completed-twice-with-results-compared
      - load-test-run-twice-with-regression-review-completed
      - governance-loops-evidenced-at-second-cycle
      - runbooks-executed-by-non-authors-with-records
      - sustained-operation-declaration-approved-by-executive-sponsor
program_milestones:
  - id: m0-1
    status: completed
    epic_id: epic-0
    name: governance-baseline-frozen
    deliverables:
      - approved-core-adrs
      - ownership-matrix-by-role
      - escalation-and-exception-model
    acceptance: core decisions ownership and escalation rules are approved and can be used without reinterpretation by downstream epics
  - id: m0-2
    status: completed
    epic_id: epic-0
    name: execution-governance-operationalized
    deliverables:
      - operating-rules-for-agents
      - program-level-definition-of-done
      - approved-wave-1-sequencing-rules
    acceptance: program execution rules are explicit audit-first and stable enough to gate all later work packages
  - id: m1-1
    status: completed
    epic_id: epic-1
    name: taxonomy-and-metadata-contract-approved
    deliverables:
      - wave-1-document-taxonomy
      - metadata-schema-version-1
      - naming-and-linking-rules
    acceptance: canonical document structure can be validated automatically and supports registry binding retrieval filtering and governance review
  - id: m1-2
    status: completed
    epic_id: epic-1
    name: canonical-template-pack-published
    deliverables:
      - wave-1-template-pack
      - validation-rules
      - adoption-guidance-for-document-authors
    acceptance: target wave-1 document classes can be authored consistently reviewed and bound to registry entities without ad-hoc interpretation
  - id: m2-1
    status: in-progress
    epic_id: epic-2
    name: logical-registry-model-approved
    deliverables:
      - entity-relationship-model
      - state-separation-rules
      - provenance-model
    acceptance: the logical model covers real wave-1 infrastructure services applications and evidence relationships without unresolved semantic ambiguity
  - id: m2-2
    status: in-progress
    epic_id: epic-2
    name: physical-schema-and-query-contracts-approved
    deliverables:
      - physical-table-design
      - constraint-and-index-strategy
      - query-contracts-for-retrieval-reconciliation-and-audit
    acceptance: the planned schema supports the required operational queries and enforces the main integrity boundaries without procedural workarounds
  - id: m2-3
    status: in-progress
    epic_id: epic-2
    name: migration-and-reference-data-baseline-ready
    deliverables:
      - migration-chain-v1
      - seed-reference-taxonomies
      - data-dictionary-and-db-comments
    acceptance: schema evolution can start from empty state repeatably and all core tables and columns are documented for implementers and reviewers
  - id: m3-1
    status: in-progress
    epic_id: epic-3
    name: wave-1-discovery-source-contracts-approved
    deliverables:
      - prioritized-source-inventory
      - normalization-contracts
      - provenance-capture-contract
    acceptance: each approved discovery source has a defined mapping path into the registry and a reviewable provenance model
  - id: m3-2
    status: in-progress
    epic_id: epic-3
    name: repeatable-loaders-and-first-ingestion-live
    deliverables:
      - loader-compatible-producer-format
      - repeatable-loaders
      - first-targeted-ingestion-run
    acceptance: normalized observed facts can be loaded into the registry repeatedly without manual SQL repairs or non-audited transformations
  - id: m3-3
    status: in-progress
    epic_id: epic-3
    name: full-reconciliation-baseline-approved
    deliverables:
      - first-full-backfill
      - reconciliation-report
      - freshness-and-drift-rules
    acceptance: the platform can explain observed state provenance freshness and material gaps against canonical expectations for all reachable wave-1 assets
  - id: m4-1
    status: in-progress
    epic_id: epic-4
    name: task-type-and-evidence-contracts-approved
    deliverables:
      - supported-task-type-catalog
      - evidence-pack-schema
      - inclusion-and-exclusion-rules
    acceptance: every supported task type has an explicit bounded evidence contract with mandatory recommended and disallowed context classes
  - id: m4-2
    status: in-progress
    epic_id: epic-4
    name: deterministic-first-retrieval-path-implemented
    deliverables:
      - exact-and-filtered-query-layer
      - lexical-search-layer
      - policy-bounded-context-assembly-rules
    acceptance: retrieval order is enforced from structured sources toward semantic complements and cannot silently skip deterministic filtering
  - id: m4-3
    status: in-progress
    epic_id: epic-4
    name: semantic-augmentation-and-bounded-context-quality-validated
    deliverables:
      - chunking-and-embedding-pipeline
      - ranking-and-selection-rationale-model
      - validation-results-on-real-wave-1-tasks
    acceptance: semantic augmentation improves bounded context packs without breaking provenance ordering scope control or auditability
  - id: m5-1
    status: in-progress
    epic_id: epic-5
    name: policy-matrix-and-risk-classes-approved
    deliverables:
      - task-class-policy-matrix
      - tool-and-action-risk-classification
      - deny-path-definition
    acceptance: every supported action class has explicit permissions approval needs evidence requirements and blocking rules
  - id: m5-2
    status: in-progress
    epic_id: epic-5
    name: mediated-action-and-approval-ledger-operational
    deliverables:
      - action-request-contract
      - approval-ledger
      - enforcement-rules-for-scope-intent-and-expiry
    acceptance: no governed write path can execute outside a persisted approval-bound action workflow
  - id: m5-3
    status: in-progress
    epic_id: epic-5
    name: agent-run-audit-and-prompt-governance-live
    deliverables:
      - prompt-template-registry
      - agent-run-ledger
      - verification-for-denied-and-approved-execution-paths
    acceptance: material agent runs are fully auditable and unsupported or unapproved writes are denied by default
  - id: m6-1
    status: in-progress
    epic_id: epic-6
    name: pilot-scope-and-artifact-pack-approved
    deliverables:
      - approved-bounded-pilot-scope
      - research-dossier
      - application-definition-pack
      - verification-specification-and-evidence-map
    acceptance: the selected pilot has a complete approved artifact set tied to real dependencies constraints and success criteria
  - id: m6-2
    status: in-progress
    epic_id: epic-6
    name: first-governed-pilot-run-completed
    deliverables:
      - full-brokered-context-pack
      - approval-gated-execution-record
      - post-run-verification-record
    acceptance: the pilot executes end-to-end through governed platform paths with no hidden manual bypasses and with complete audit evidence
  - id: m6-3
    status: in-progress
    epic_id: epic-6
    name: repeatability-and-gap-honesty-validated
    deliverables:
      - second-run-delta-report
      - residual-gap-register
      - platform-improvement-backlog-derived-from-pilot
    acceptance: repeatability is proven or disproven honestly and every remaining manual dependency is recorded as a platform gap
  - id: m7-1
    status: in-progress
    epic_id: epic-7
    name: kpi-observability-and-alerting-active
    deliverables:
      - kpi-and-slo-catalog
      - dashboards-for-core-surfaces
      - alerting-rules-linked-to-runbooks
    acceptance: operators can detect and interpret failures or degradation across registry discovery retrieval and control-plane flows
  - id: m7-2
    status: in-progress
    epic_id: epic-7
    name: audit-retention-and-runbook-model-approved
    deliverables:
      - retention-policy
      - audit-review-workflows
      - runbooks-for-critical-scenarios
    acceptance: audit artifacts have enforceable retention and access rules and every critical alert path has an operational runbook
  - id: m7-3
    status: in-progress
    epic_id: epic-7
    name: wave-2-readiness-review-recorded
    deliverables:
      - honest-gap-register
      - residual-risk-register
      - formal-go-or-hold-decision
    acceptance: expansion beyond wave-1 is gated by evidence-backed readiness review rather than narrative optimism
  - id: m7-4
    status: in-progress
    epic_id: epic-7
    name: shared-observability-signal-contracts-and-ownership-approved
    deliverables:
      - observability-signal-inventory
      - metrics-logs-traces-and-events-contracts
      - signal-ownership-matrix
    acceptance: every critical platform surface exposes approved signals with named owners source definitions and operational purpose
  - id: m7-5
    status: in-progress
    epic_id: epic-7
    name: grafana-shared-dashboards-alert-routing-and-slo-views-live
    deliverables:
      - shared-grafana-dashboard-pack
      - alert-routing-and-contact-point-matrix
      - kpi-slo-and-error-budget-views
    acceptance: shared observability on orchestrator exposes actionable dashboards and tested alert routes for all critical wave-1 surfaces
  - id: m7-6
    status: in-progress
    epic_id: epic-7
    name: observability-retention-runbook-linkage-and-gameday-verified
    deliverables:
      - retention-enforcement-validation
      - runbook-linkage-index
      - observability-gameday-report
    acceptance: retention is technically enforced critical alerts link to canonical runbooks and at least one observability drill proves the operating model under failure
  - id: m8-1
    status: in-progress
    epic_id: epic-8
    name: continuity-objectives-and-ha-posture-approved
    deliverables:
      - approved-rto-rpo-baseline
      - accepted-ha-versus-single-instance-posture
      - backup-and-recovery-scope-definition
    acceptance: business continuity expectations are explicit approved and mapped to the actual technical posture of internalCMDB
  - id: m8-2
    status: in-progress
    epic_id: epic-8
    name: backup-and-restore-path-validated
    deliverables:
      - tested-backup-procedure
      - tested-restore-procedure
      - restore-evidence-and-runtime-validation-record
    acceptance: data and critical operational artifacts can be restored within the agreed posture and the result is evidence-backed not assumed
  - id: m8-3
    status: in-progress
    epic_id: epic-8
    name: disaster-recovery-exercise-reviewed
    deliverables:
      - disaster-simulation-runbook
      - exercise-findings-report
      - corrective-actions-register
    acceptance: at least one formal recovery exercise has been executed reviewed and translated into tracked remediation actions
  - id: m9-1
    status: in-progress
    epic_id: epic-9
    name: secrets-storage-and-boundaries-approved
    deliverables:
      - secrets-storage-pattern
      - access-boundary-definition
      - bootstrap-secret-exception-register
    acceptance: privileged secrets and trust materials have an approved storage and access model instead of ad-hoc handling
  - id: m9-2
    status: in-progress
    epic_id: epic-9
    name: credential-rotation-and-role-separation-live
    deliverables:
      - rotated-bootstrap-credentials
      - role-separated-access-model
      - privileged-access-audit-evidence
    acceptance: temporary bootstrap posture is retired or constrained and credential usage is attributable by role
  - id: m9-3
    status: in-progress
    epic_id: epic-9
    name: tls-and-trust-lifecycle-operationalized
    deliverables:
      - certificate-issuance-and-renewal-model
      - trust-anchor-definition
      - certificate-failure-response-runbook
    acceptance: TLS-dependent paths have explicit issuance renewal expiry handling and recovery procedures
  - id: m10-1
    status: in-progress
    epic_id: epic-10
    name: dependency-and-artifact-inventory-baseline-established
    deliverables:
      - component-inventory
      - dependency-inventory
      - sbom-baseline
    acceptance: major packages images and third-party dependencies are inventoried and reviewable for risk and provenance
  - id: m10-2
    status: in-progress
    epic_id: epic-10
    name: scanning-and-integrity-controls-active
    deliverables:
      - dependency-scan-results
      - image-scan-results
      - integrity-policy-for-build-artifacts
    acceptance: promoted artifacts are scanned and subject to explicit integrity checks before release use
  - id: m10-3
    status: in-progress
    epic_id: epic-10
    name: provenance-and-release-attestation-approved
    deliverables:
      - artifact-provenance-model
      - signing-or-attestation-policy
      - license-review-baseline
    acceptance: release artifacts can be defended through documented provenance and policy-compliant promotion evidence
  - id: m11-1
    status: in-progress
    epic_id: epic-11
    name: environment-and-promotion-model-approved
    deliverables:
      - environment-classification
      - promotion-gates
      - release-approval-matrix
    acceptance: the program has an explicit model for how changes move between environments and who approves each class of promotion
  - id: m11-2
    status: in-progress
    epic_id: epic-11
    name: rollback-and-migration-recovery-contracts-documented
    deliverables:
      - rollback-contracts
      - migration-recovery-playbook
      - release-failure-decision-tree
    acceptance: rollback and migration recovery are planned and reviewable before being needed under pressure
  - id: m11-3
    status: in-progress
    epic_id: epic-11
    name: release-evidence-chain-operational
    deliverables:
      - deployment-evidence-records
      - release-attestation-bindings
      - post-release-verification-contract
    acceptance: each promoted release can be traced from artifact integrity through approval to post-release verification
  - id: m12-1
    status: in-progress
    epic_id: epic-12
    name: model-serving-and-registry-baseline-approved
    deliverables:
      - model-serving-stack-definition
      - model-registry-contract
      - routing-and-selection-policy
    acceptance: supported model classes have a governed serving and registration path tied to task-type usage
  - id: m12-2
    status: in-progress
    epic_id: epic-12
    name: evaluation-harness-and-benchmark-baseline-live
    deliverables:
      - evaluation-harness
      - benchmark-task-set
      - model-comparison-results
    acceptance: model choices are supported by repeatable evaluation against approved task types rather than operator preference
  - id: m12-3
    status: in-progress
    epic_id: epic-12
    name: fallback-and-safety-controls-validated
    deliverables:
      - fallback-strategy
      - latency-and-cost-guardrails
      - prompt-safety-and-red-team-check-baseline
    acceptance: model runtime behavior under failure cost and safety pressure is bounded by explicit tested controls
  - id: m13-1
    status: in-progress
    epic_id: epic-13
    name: capacity-model-and-budget-baseline-approved
    deliverables:
      - database-capacity-model
      - vector-and-broker-growth-model
      - cost-envelope-and-budget-guardrails
    acceptance: core runtime growth and cost expectations are explicit and reviewable before scale-out claims are made
  - id: m13-2
    status: in-progress
    epic_id: epic-13
    name: load-and-stress-characterization-complete
    deliverables:
      - registry-load-test-results
      - broker-latency-and-throughput-results
      - concurrency-target-baseline
    acceptance: critical surfaces have measured performance envelopes and known saturation indicators
  - id: m13-3
    status: in-progress
    epic_id: epic-13
    name: resilience-and-failure-behavior-reviewed
    deliverables:
      - failure-injection-results
      - fail-open-versus-fail-closed-rules
      - resiliency-remediation-register
    acceptance: the platform has tested and documented behavior for critical failure modes and response expectations
  - id: m14-1
    status: in-progress
    epic_id: epic-14
    name: named-raci-and-service-boundaries-approved
    deliverables:
      - named-raci-matrix
      - service-boundary-map
      - ownership-acceptance-records
    acceptance: critical services capabilities and reviews have accountable named owners not only abstract roles
  - id: m14-2
    status: in-progress
    epic_id: epic-14
    name: support-tiers-and-on-call-model-operational
    deliverables:
      - l1-l2-l3-support-model
      - on-call-and-escalation-rules
      - incident-command-baseline
    acceptance: incidents and operator issues can be routed escalated and owned without ambiguity
  - id: m14-3
    status: in-progress
    epic_id: epic-14
    name: recurring-service-operations-cadence-active
    deliverables:
      - service-review-cadence
      - privileged-access-review-cadence
      - incident-review-cadence
    acceptance: the platform has recurring human governance loops that reduce post-launch governance drift
  - id: m15-1
    status: in-progress
    epic_id: epic-15
    name: data-classification-and-redaction-controls-approved
    deliverables:
      - data-classification-matrix
      - ingest-redaction-policy
      - access-control-model-for-classified-data
    acceptance: all registry data classes are defined with explicit restrictions and ingest-time redaction for sensitive patterns is operational and tested against real collection scenarios
  - id: m15-2
    status: in-progress
    epic_id: epic-15
    name: retention-deletion-and-exception-governance-active
    deliverables:
      - retention-and-deletion-runbook
      - exception-register-baseline
      - change-log-entries-for-data-governance-decisions
    acceptance: data retention rules are documented and tested per class and any policy exceptions are tracked in the governed exception register with explicit approvals
  - id: m15-3
    status: in-progress
    epic_id: epic-15
    name: data-governance-compliance-declaration-approved
    deliverables:
      - data-governance-compliance-declaration
      - quarterly-access-review-cadence-record-cycle-1
    acceptance: executive sponsor has approved the compliance declaration confirming classification controls are active and the first quarterly access review has been completed and documented
  - id: m16-1
    status: in-progress
    epic_id: epic-16
    name: second-cycle-drills-and-load-tests-completed
    deliverables:
      - backup-restore-drill-evidence-cycle-2
      - load-test-results-v2-with-comparison-report
      - model-evaluation-results-cycle-2-with-regression-summary
    acceptance: backup restore drill and load test have each been executed at least twice with cycle-2 results explicitly compared against cycle-1 for regression
  - id: m16-2
    status: in-progress
    epic_id: epic-16
    name: recurring-governance-loops-evidenced-at-second-cycle
    deliverables:
      - privileged-access-review-record-cycle-2
      - service-review-minutes-cycle-2
      - alert-response-drill-record
      - runbook-execution-records-pack
    acceptance: privileged access review and service review have each been completed at least twice and at least three runbooks have been executed by operators other than the original authors with records stored
  - id: m16-3
    status: in-progress
    epic_id: epic-16
    name: sustained-operation-declaration-approved
    deliverables:
      - sustained-operation-declaration
      - governance-change-log-activity-baseline
    acceptance: executive sponsor has approved the formal sustained operation declaration listing all recurring loops executed at least twice and the change log shows at least 10 post-deployment entries from normal operations confirming the platform is operated not only deployed
program_sprints:
  - id: sprint-1
    status: in-progress
    duration: 1-to-2-weeks
    goal: freeze governance baseline and establish canonical document governance foundations
    epic_ids: [epic-0, epic-1]
    milestone_ids: [m0-1, m1-1]
  - id: sprint-2
    status: in-progress
    duration: 1-to-2-weeks
    goal: publish the wave-1 canonical template pack and approve the logical registry model
    epic_ids: [epic-1, epic-2]
    milestone_ids: [m0-2, m1-2, m2-1]
  - id: sprint-3
    status: in-progress
    duration: 2-weeks
    goal: approve the physical registry schema migration baseline and query contracts
    epic_ids: [epic-2]
    milestone_ids: [m2-2, m2-3]
  - id: sprint-4
    status: in-progress
    duration: 1-to-2-weeks
    goal: define wave-1 discovery contracts and start repeatable ingestion
    epic_ids: [epic-3]
    milestone_ids: [m3-1, m3-2]
  - id: sprint-5
    status: in-progress
    duration: 1-to-2-weeks
    goal: complete the first full reconciliation baseline and stabilize observed-state governance
    epic_ids: [epic-3]
    milestone_ids: [m3-3]
  - id: sprint-6
    status: in-progress
    duration: 2-weeks
    goal: define evidence contracts and implement deterministic-first retrieval
    epic_ids: [epic-4]
    milestone_ids: [m4-1, m4-2]
  - id: sprint-7
    status: in-progress
    duration: 1-to-2-weeks
    goal: validate semantic augmentation and approve the control-plane policy matrix
    epic_ids: [epic-4, epic-5]
    milestone_ids: [m4-3, m5-1]
  - id: sprint-8
    status: in-progress
    duration: 2-weeks
    goal: operationalize mediated approvals and prepare the pilot artifact pack
    epic_ids: [epic-5, epic-6]
    milestone_ids: [m5-2, m6-1]
  - id: sprint-9
    status: in-progress
    duration: 2-weeks
    goal: complete agent audit governance and execute the first governed pilot run
    epic_ids: [epic-5, epic-6, epic-7]
    milestone_ids: [m5-3, m6-2, m7-1]
  - id: sprint-10
    status: in-progress
    duration: 1-to-2-weeks
    goal: validate repeatability and publish retention and runbook controls
    epic_ids: [epic-6, epic-7]
    milestone_ids: [m6-3, m7-2]
  - id: sprint-11
    status: in-progress
    duration: 1-week
    goal: complete the evidence-based readiness review for controlled expansion beyond wave-1
    epic_ids: [epic-7]
    milestone_ids: [m7-3]
  - id: sprint-12
    status: in-progress
    duration: 1-to-2-weeks
    goal: approve continuity objectives and define backup and recovery scope for internalcmdb
    epic_ids: [epic-8]
    milestone_ids: [m8-1]
  - id: sprint-13
    status: in-progress
    duration: 2-weeks
    goal: validate restore paths and establish secrets storage and trust boundaries
    epic_ids: [epic-8, epic-9]
    milestone_ids: [m8-2, m8-3, m9-1]
  - id: sprint-14
    status: in-progress
    duration: 2-weeks
    goal: rotate bootstrap credentials and establish software integrity baselines
    epic_ids: [epic-9, epic-10]
    milestone_ids: [m9-2, m9-3, m10-1]
  - id: sprint-15
    status: in-progress
    duration: 2-weeks
    goal: activate artifact integrity controls and approve environment promotion governance
    epic_ids: [epic-10, epic-11]
    milestone_ids: [m10-2, m10-3, m11-1]
  - id: sprint-16
    status: in-progress
    duration: 2-weeks
    goal: document rollback contracts and approve model serving and registry governance
    epic_ids: [epic-11, epic-12]
    milestone_ids: [m11-2, m11-3, m12-1]
  - id: sprint-17
    status: in-progress
    duration: 2-weeks
    goal: operationalize evaluation harnesses and approve capacity modeling baselines
    epic_ids: [epic-12, epic-13]
    milestone_ids: [m12-2, m12-3, m13-1]
  - id: sprint-18
    status: in-progress
    duration: 2-weeks
    goal: characterize load and failure behavior while finalizing named service ownership
    epic_ids: [epic-13, epic-14]
    milestone_ids: [m13-2, m13-3, m14-1]
  - id: sprint-19
    status: in-progress
    duration: 1-to-2-weeks
    goal: activate support cadence and recurring operational governance loops
    epic_ids: [epic-14]
    milestone_ids: [m14-2, m14-3]
  - id: sprint-20
    status: in-progress
    duration: 1-to-2-weeks
    goal: define shared observability signal inventory instrumentation contracts and ownership for all critical wave-1 surfaces
    epic_ids: [epic-7]
    milestone_ids: [m7-4]
  - id: sprint-21
    status: in-progress
    duration: 2-weeks
    goal: implement grafana shared dashboards alert routing and slo or error-budget visualization for wave-1
    epic_ids: [epic-7]
    milestone_ids: [m7-5]
  - id: sprint-22
    status: in-progress
    duration: 1-to-2-weeks
    goal: verify retention enforcement runbook linkage and observability drill readiness on live surfaces
    epic_ids: [epic-7]
    milestone_ids: [m7-6]
  - id: sprint-23
    status: in-progress
    duration: 2-weeks
    goal: activate data classification redaction controls and retention governance for the registry and approve the compliance declaration
    epic_ids: [epic-15]
    milestone_ids: [m15-1, m15-2, m15-3]
  - id: sprint-24
    status: in-progress
    duration: 2-to-3-weeks
    goal: complete second-cycle operational drills load tests governance reviews and approve the formal sustained operation declaration as the wave-2 readiness gate
    epic_ids: [epic-16]
    milestone_ids: [m16-1, m16-2, m16-3]
program_tasks:
  - id: pt-001
    status: completed
    epic_id: epic-0
    sprint_id: sprint-1
    milestone_id: m0-1
    name: extract-and-freeze-core-adrs-from-blueprint-and-approved-live-findings
    deliverable: approved ADR set covering truth model system-of-record retrieval ordering write approval and rollout discipline
    verification: ADR review completed by architecture board with explicit accepted and rejected alternatives
  - id: pt-002
    status: completed
    epic_id: epic-0
    sprint_id: sprint-1
    milestone_id: m0-1
    name: define-role-based-ownership-matrix-and-escalation-authority
    deliverable: ownership matrix by platform role with named approval authority requirements and escalation paths
    verification: ownership coverage review confirms no critical capability lacks a responsible role or approver class
  - id: pt-003
    status: completed
    epic_id: epic-0
    sprint_id: sprint-2
    milestone_id: m0-2
    name: formalize-agent-operating-rules-definition-of-done-and-sequencing-gates
    deliverable: executable governance baseline for handoffs verification and status progression
    verification: downstream epics can reference stable execution rules without adding local policy exceptions
  - id: pt-004
    status: completed
    epic_id: epic-1
    sprint_id: sprint-1
    milestone_id: m1-1
    name: define-wave-1-document-classes-identifiers-and-binding-rules
    deliverable: canonical taxonomy for infrastructure shared services applications governance and runbook artifacts
    verification: each document class has identifier owner status and registry-binding semantics reviewable by rule
  - id: pt-005
    status: completed
    epic_id: epic-1
    sprint_id: sprint-1
    milestone_id: m1-1
    name: author-metadata-schema-frontmatter-rules-and-link-conventions
    deliverable: versioned metadata contract with mandatory recommended and optional fields plus linking grammar
    verification: metadata validation succeeds on representative real wave-1 documents and rejects malformed bindings
  - id: pt-006
    status: completed
    epic_id: epic-1
    sprint_id: sprint-2
    milestone_id: m1-2
    name: publish-template-pack-validation-rules-and-author-guidance
    deliverable: reusable template pack and documentation for disciplined authoring and review
    verification: a new wave-1 canonical document can be created validated and approved without ad-hoc coaching
  - id: pt-007
    status: in-progress
    epic_id: epic-2
    sprint_id: sprint-2
    milestone_id: m2-1
    name: model-core-entities-relationships-state-separation-and-provenance
    deliverable: approved logical registry model spanning hosts clusters services applications evidence and ownership relations
    verification: logical review against blueprint and live infrastructure shows no unresolved entity-class ambiguity for wave-1
  - id: pt-008
    status: in-progress
    epic_id: epic-2
    sprint_id: sprint-3
    milestone_id: m2-2
    name: define-physical-schema-constraints-indexes-and-query-contracts
    deliverable: physical database design with query surfaces for retrieval reconciliation operational lookup and audit
    verification: required query classes can be expressed cleanly without hidden procedural joins or unchecked JSON blobs
  - id: pt-009
    status: in-progress
    epic_id: epic-2
    sprint_id: sprint-3
    milestone_id: m2-3
    name: author-migration-chain-seed-reference-data-and-data-dictionary
    deliverable: repeatable schema migration baseline with seeded taxonomies comments and dictionary coverage
    verification: empty-to-head migration path runs cleanly and every core table and column has reviewed documentation
  - id: pt-010
    status: in-progress
    epic_id: epic-3
    sprint_id: sprint-4
    milestone_id: m3-1
    name: inventory-approved-wave-1-discovery-sources-and-normalization-contracts
    deliverable: source inventory and normalized mapping contracts for approved read-only collectors and their outputs
    verification: every in-scope source maps to registry targets with provenance and freshness semantics defined
  - id: pt-011
    status: in-progress
    epic_id: epic-3
    sprint_id: sprint-4
    milestone_id: m3-2
    name: adapt-approved-audit-assets-into-loader-compatible-producers-and-repeatable-loaders
    deliverable: structured producer outputs and loaders for registry ingestion without manual SQL fixes
    verification: targeted ingestion runs succeed reproducibly and preserve source provenance end-to-end
  - id: pt-012
    status: in-progress
    epic_id: epic-3
    sprint_id: sprint-5
    milestone_id: m3-3
    name: execute-first-full-backfill-and-produce-reconciliation-baseline
    deliverable: full wave-1 ingestion run plus reconciliation report with drift freshness and unresolved gap classification
    verification: reviewers can trace each major observed fact to source time collector and normalized registry representation
  - id: pt-013
    status: in-progress
    epic_id: epic-4
    sprint_id: sprint-6
    milestone_id: m4-1
    name: define-supported-task-types-and-evidence-pack-contracts
    deliverable: task-type catalog and evidence-pack schema with mandatory recommended and disallowed context classes
    verification: each supported task type has an explicit bounded context definition accepted by architecture and policy owners
  - id: pt-014
    status: in-progress
    epic_id: epic-4
    sprint_id: sprint-6
    milestone_id: m4-2
    name: implement-deterministic-first-retrieval-and-policy-bounded-context-assembly
    deliverable: retrieval flow that prioritizes exact lookup metadata filtering and lexical search before semantic augmentation
    verification: controlled tests prove retrieval ordering and show that bounded filters are enforced before semantic stages
  - id: pt-015
    status: in-progress
    epic_id: epic-4
    sprint_id: sprint-7
    milestone_id: m4-3
    name: implement-semantic-augmentation-chunking-ranking-and-selection-rationale
    deliverable: approved semantic complement path with chunk lineage vector versioning reranking and rationale capture
    verification: real wave-1 tasks demonstrate improved context quality without loss of provenance or scope discipline
  - id: pt-016
    status: in-progress
    epic_id: epic-5
    sprint_id: sprint-7
    milestone_id: m5-1
    name: define-policy-matrix-risk-classes-and-deny-by-default-rules
    deliverable: formal policy matrix across read-only analysis repo writes bounded runtime changes and high-risk infrastructure actions
    verification: every supported action class has explicit evidence approval and post-execution verification requirements
  - id: pt-017
    status: in-progress
    epic_id: epic-5
    sprint_id: sprint-8
    milestone_id: m5-2
    name: implement-mediated-action-requests-approvals-and-scope-expiry-enforcement
    deliverable: persisted approval-bound action workflow enforcing scope intent expiry and outcome capture
    verification: no governed write path can execute in tests or review flows without an eligible approval record
  - id: pt-018
    status: in-progress
    epic_id: epic-5
    sprint_id: sprint-9
    milestone_id: m5-3
    name: operationalize-prompt-template-governance-and-agent-run-audit-ledger
    deliverable: versioned prompt registry plus run and evidence ledger for material agent execution
    verification: denied and approved runs both leave sufficient audit records to reconstruct policy application and evidence usage
  - id: pt-019
    status: in-progress
    epic_id: epic-6
    sprint_id: sprint-8
    milestone_id: m6-1
    name: select-bounded-pilot-and-author-the-mandatory-artifact-pack
    deliverable: approved pilot scope plus research dossier application definition pack verification specification and evidence map
    verification: domain and program reviewers confirm that the pilot is bounded realistic and fully documented against real dependencies
  - id: pt-020
    status: in-progress
    epic_id: epic-6
    sprint_id: sprint-9
    milestone_id: m6-2
    name: execute-the-first-governed-pilot-run-through-brokers-and-approvals
    deliverable: end-to-end pilot execution record with brokered context approved actions verification evidence and audit completeness
    verification: reviewers confirm that no hidden manual step was needed to achieve the declared pilot outcome
  - id: pt-021
    status: in-progress
    epic_id: epic-6
    sprint_id: sprint-10
    milestone_id: m6-3
    name: repeat-the-pilot-run-and-record-all-residual-platform-gaps
    deliverable: repeatability delta report and honest residual gap register derived from the second governed run
    verification: the second run either reproduces the first result or surfaces concrete missing platform capabilities with evidence
  - id: pt-022
    status: in-progress
    epic_id: epic-7
    sprint_id: sprint-9
    milestone_id: m7-1
    name: define-kpis-slos-dashboards-and-alerting-for-core-platform-surfaces
    deliverable: observability catalog and live dashboards for registry discovery retrieval approvals and agent control surfaces
    verification: failure and degradation scenarios can be detected interpreted and assigned through reviewable signals
  - id: pt-023
    status: in-progress
    epic_id: epic-7
    sprint_id: sprint-10
    milestone_id: m7-2
    name: implement-retention-audit-review-workflows-and-critical-runbooks
    deliverable: retention enforcement audit review process and runbooks for ingestion retrieval approval and broker-failure scenarios
    verification: critical alerts have linked runbooks and audit artifacts have enforceable retention and access controls
  - id: pt-024
    status: in-progress
    epic_id: epic-7
    sprint_id: sprint-11
    milestone_id: m7-3
    name: conduct-the-wave-2-readiness-review-with-explicit-gap-and-risk-registers
    deliverable: formal readiness package containing residual risks open gaps approved exceptions and go-or-hold recommendation
    verification: expansion decision is traceable to objective evidence from pilot audit observability and governance reviews
  - id: pt-025
    status: in-progress
    epic_id: epic-8
    sprint_id: sprint-12
    milestone_id: m8-1
    name: define-rto-rpo-ha-posture-and-continuity-scope-for-internalcmdb
    deliverable: approved continuity baseline including accepted availability posture and recovery expectations
    verification: sponsor and runtime owners sign off that recovery expectations match the actual intended operating model
  - id: pt-026
    status: in-progress
    epic_id: epic-8
    sprint_id: sprint-13
    milestone_id: m8-2
    name: implement-and-test-backup-and-restore-procedures-for-data-and-critical-artifacts
    deliverable: tested backup and restore path with evidence of runtime recovery and artifact integrity
    verification: restore exercise completes within the declared posture and recovered state passes reviewable validation checks
  - id: pt-027
    status: in-progress
    epic_id: epic-8
    sprint_id: sprint-13
    milestone_id: m8-3
    name: execute-a-formal-disaster-recovery-simulation-and-record-remediation-actions
    deliverable: disaster exercise report with findings risk rating and corrective action register
    verification: reviewers can trace exercise steps outcomes and post-exercise improvements without relying on oral history
  - id: pt-028
    status: in-progress
    epic_id: epic-9
    sprint_id: sprint-13
    milestone_id: m9-1
    name: approve-secrets-storage-pattern-and-trust-boundaries-for-platform-components
    deliverable: approved secret storage and trust boundary model for runtime credentials keys and certificates
    verification: every privileged secret class maps to an owner storage boundary and access rule
  - id: pt-029
    status: in-progress
    epic_id: epic-9
    sprint_id: sprint-14
    milestone_id: m9-2
    name: rotate-bootstrap-credentials-and-enforce-role-separated-privileged-access
    deliverable: reduced bootstrap exposure and role-separated privileged credential posture
    verification: temporary bootstrap credentials are retired or constrained and privileged access is auditable by role
  - id: pt-030
    status: in-progress
    epic_id: epic-9
    sprint_id: sprint-14
    milestone_id: m9-3
    name: define-certificate-lifecycle-renewal-and-trust-recovery-procedures
    deliverable: TLS lifecycle policy with issuance renewal expiry and failure handling procedures
    verification: certificate-dependent flows can be renewed and recovered through explicit documented steps
  - id: pt-031
    status: in-progress
    epic_id: epic-10
    sprint_id: sprint-14
    milestone_id: m10-1
    name: inventory-dependencies-images-and-third-party-sources-and-produce-sbom-baseline
    deliverable: reviewed inventory and SBOM baseline for core software components and runtime artifacts
    verification: major dependency and artifact sources are traceable and classifiable for risk review
  - id: pt-032
    status: in-progress
    epic_id: epic-10
    sprint_id: sprint-15
    milestone_id: m10-2
    name: activate-dependency-and-image-scanning-with-reviewable-integrity-gates
    deliverable: scanning pipeline and policy gates for code packages and container images
    verification: artifacts with critical unresolved issues are blocked or escalated according to recorded policy
  - id: pt-033
    status: in-progress
    epic_id: epic-10
    sprint_id: sprint-15
    milestone_id: m10-3
    name: approve-artifact-provenance-attestation-and-license-review-policy
    deliverable: provenance and attestation model tied to release classes and license review obligations
    verification: promoted artifacts can be defended through provenance evidence and policy-compliant attestation records
  - id: pt-034
    status: in-progress
    epic_id: epic-11
    sprint_id: sprint-15
    milestone_id: m11-1
    name: define-environment-classes-promotion-gates-and-release-approval-model
    deliverable: explicit promotion and approval contract for each environment and release class
    verification: release reviewers can determine who approves what and under which gate without ambiguity
  - id: pt-035
    status: in-progress
    epic_id: epic-11
    sprint_id: sprint-16
    milestone_id: m11-2
    name: document-rollback-contracts-and-run-migration-recovery-drills
    deliverable: rollback playbooks and exercised migration recovery procedures for database-bearing changes
    verification: rollback and migration recovery can be followed under drill conditions without ad-hoc invention
  - id: pt-036
    status: in-progress
    epic_id: epic-11
    sprint_id: sprint-16
    milestone_id: m11-3
    name: implement-release-evidence-chains-from-artifact-integrity-to-post-release-verification
    deliverable: linked evidence records for release decisions deployment execution and post-release validation
    verification: any promoted release can be reconstructed end-to-end from approved artifact to verified outcome
  - id: pt-037
    status: in-progress
    epic_id: epic-12
    sprint_id: sprint-16
    milestone_id: m12-1
    name: define-model-serving-stack-registry-contract-and-routing-rules
    deliverable: governed runtime and model registry contract for supported self-hosted model classes
    verification: model selection and routing decisions are explicit and tied to approved task-type usage rules
  - id: pt-038
    status: in-progress
    epic_id: epic-12
    sprint_id: sprint-17
    milestone_id: m12-2
    name: implement-evaluation-harness-and-benchmark-suite-for-supported-task-types
    deliverable: repeatable evaluation process and comparative benchmark results for target model classes
    verification: model evaluation can be rerun and produces reviewable evidence for selection or rejection decisions
  - id: pt-039
    status: in-progress
    epic_id: epic-12
    sprint_id: sprint-17
    milestone_id: m12-3
    name: define-fallback-latency-cost-and-safety-controls-for-model-runtime-behavior
    deliverable: fallback and guardrail policy with tested safety and runtime degradation handling
    verification: failure or overload conditions trigger documented bounded behaviors instead of operator improvisation
  - id: pt-040
    status: in-progress
    epic_id: epic-13
    sprint_id: sprint-17
    milestone_id: m13-1
    name: produce-capacity-growth-and-cost-models-for-database-vector-and-broker-surfaces
    deliverable: capacity and cost baseline covering storage growth query load and concurrency expectations
    verification: expected growth and cost envelopes are explicit enough to support planning and scale decisions
  - id: pt-041
    status: in-progress
    epic_id: epic-13
    sprint_id: sprint-18
    milestone_id: m13-2
    name: execute-load-and-stress-tests-for-registry-retrieval-and-control-surfaces
    deliverable: performance characterization results for critical platform paths under expected and stressed conditions
    verification: critical surfaces have measured latency throughput and saturation points with findings recorded
  - id: pt-042
    status: in-progress
    epic_id: epic-13
    sprint_id: sprint-18
    milestone_id: m13-3
    name: run-failure-injection-exercises-and-document-fail-open-versus-fail-closed-behavior
    deliverable: resilience review pack describing tested failure behavior and remediation priorities
    verification: fail behavior for core components is evidence-backed and aligned with policy and safety goals
  - id: pt-043
    status: in-progress
    epic_id: epic-14
    sprint_id: sprint-18
    milestone_id: m14-1
    name: finalize-named-raci-and-map-service-boundaries-to-real-owners
    deliverable: named responsibility matrix and accepted service ownership model
    verification: no critical capability remains without a named owner or review authority
  - id: pt-044
    status: in-progress
    epic_id: epic-14
    sprint_id: sprint-19
    milestone_id: m14-2
    name: establish-support-tiers-on-call-rules-and-incident-command-baseline
    deliverable: support and escalation operating model for critical services and incidents
    verification: incident and operator escalation can be executed through named roles and reviewable paths
  - id: pt-045
    status: in-progress
    epic_id: epic-14
    sprint_id: sprint-19
    milestone_id: m14-3
    name: activate-recurring-service-access-and-incident-review-cadences
    deliverable: operational review calendar and recurring governance rituals for service health and privileged access
    verification: recurring reviews are scheduled owned and capable of catching governance drift over time
  - id: pt-046
    status: in-progress
    epic_id: epic-7
    sprint_id: sprint-20
    milestone_id: m7-4
    name: define-observability-signal-inventory-and-ownership-for-registry-discovery-retrieval-and-control-plane
    deliverable: approved inventory of critical metrics logs traces events and derived health queries with named owners and purpose
    verification: each critical platform surface has reviewable signals and no alert-worthy condition depends on unnamed or undefined telemetry
  - id: pt-047
    status: in-progress
    epic_id: epic-7
    sprint_id: sprint-20
    milestone_id: m7-4
    name: define-instrumentation-and-export-contracts-to-shared-prometheus-loki-and-related-sources
    deliverable: instrumentation contract describing how signals are emitted collected labeled retained and queried on shared observability surfaces
    verification: signal collection paths are explicit and sufficient to support dashboards alerts and investigations without hidden local-only knowledge
  - id: pt-048
    status: in-progress
    epic_id: epic-7
    sprint_id: sprint-20
    milestone_id: m7-4
    name: define-canonical-health-queries-and-derived-status-rules-for-critical-wave-1-surfaces
    deliverable: approved health query pack and derived status rules for registry freshness ingestion retrieval approvals and agent runs
    verification: operators can derive health states from documented queries and not only from dashboard visuals
  - id: pt-049
    status: in-progress
    epic_id: epic-7
    sprint_id: sprint-21
    milestone_id: m7-5
    name: implement-shared-grafana-dashboard-pack-for-registry-discovery-retrieval-and-agent-governance
    deliverable: organized grafana shared dashboards and drill-down views for platform state freshness quality audit and denial analysis
    verification: each critical workflow has an actionable dashboard view with provenance to the underlying signal sources
  - id: pt-050
    status: in-progress
    epic_id: epic-7
    sprint_id: sprint-21
    milestone_id: m7-5
    name: implement-alert-routing-contact-points-and-escalation-rules-for-critical-operational-signals
    deliverable: tested alert routing model covering collector failures drift spikes approval expiries broker anomalies and ingestion degradation
    verification: synthetic or controlled alerts prove routing ownership escalation and acknowledgment behavior on shared observability surfaces
  - id: pt-051
    status: in-progress
    epic_id: epic-7
    sprint_id: sprint-21
    milestone_id: m7-5
    name: implement-kpi-slo-and-error-budget-views-backed-by-approved-thresholds-or-approval-candidates
    deliverable: operational KPI SLO and error-budget views for freshness evidence completeness approvals alert actionability and audit completeness
    verification: each displayed KPI or SLO is traceable to a documented definition threshold and query source
  - id: pt-052
    status: in-progress
    epic_id: epic-7
    sprint_id: sprint-22
    milestone_id: m7-6
    name: implement-and-validate-retention-enforcement-on-audit-evidence-agent-run-and-collection-artifact-classes
    deliverable: technical enforcement and validation record for retention classes deletion suspension exceptions and access boundaries
    verification: retention behavior matches approved classes and does not silently break auditability inside the declared retention windows
  - id: pt-053
    status: in-progress
    epic_id: epic-7
    sprint_id: sprint-22
    milestone_id: m7-6
    name: build-runbook-linkage-index-between-critical-alerts-grafana-views-and-canonical-operational-documents
    deliverable: indexed linkage from alert rules and dashboard panels to runbooks owners escalation paths and recovery procedures
    verification: every critical alert path can reach an approved runbook and owner without relying on institutional memory
  - id: pt-054
    status: in-progress
    epic_id: epic-7
    sprint_id: sprint-22
    milestone_id: m7-6
    name: execute-observability-gameday-for-failed-collector-drift-spike-approval-expiry-and-broker-anomaly-scenarios
    deliverable: observability drill report with detected gaps response timing false positives false negatives and corrective actions
    verification: at least one end-to-end drill proves that signals alerts dashboards runbooks and escalation paths work together under realistic failure conditions
  - id: pt-055
    status: in-progress
    epic_id: epic-15
    sprint_id: sprint-23
    milestone_id: m15-1
    name: author-and-approve-data-classification-matrix
    deliverable: policy_pack document with data classes A through D including examples restrictions and owner slot per class
    verification: all registry tables can be mapped to at least one class and no column carrying IP credentials or accounts is left unclassified
  - id: pt-056
    status: in-progress
    epic_id: epic-15
    sprint_id: sprint-23
    milestone_id: m15-1
    name: implement-ingest-time-redaction-scanner-and-rejection-control
    deliverable: scanner component integrated with the collection pipeline that rejects observed_fact or chunk records containing credential patterns and logs the rejection in the collection_run record
    verification: at least three injection test cases with real credential patterns are correctly rejected and none reach the registry tables
  - id: pt-057
    status: in-progress
    epic_id: epic-15
    sprint_id: sprint-23
    milestone_id: m15-1
    name: define-and-activate-access-control-model-for-classified-data
    deliverable: access control rules for class B and class C registry data with role check enforcement at query time and retrieval exclusion for unauthorized callers
    verification: a caller without the platform_engineering role cannot retrieve class B facts through the retrieval broker and the denial is logged
  - id: pt-058
    status: in-progress
    epic_id: epic-15
    sprint_id: sprint-23
    milestone_id: m15-2
    name: author-retention-and-deletion-runbooks-per-data-class
    deliverable: documented and tested retention and deletion procedure for observed_fact, agent_run, evidence_pack and chunk_embedding per class with passo-by-step validation
    verification: a test deletion run against non-production data confirms correct records are removed and foreign key constraints behave as expected
  - id: pt-059
    status: in-progress
    epic_id: epic-15
    sprint_id: sprint-23
    milestone_id: m15-2
    name: establish-exception-register-and-data-governance-escalation-model
    deliverable: exception register baseline in governance.change_log with escalation rule that any open exception without remediation plan after 30 days triggers security_and_policy_owner review
    verification: at least one synthetic exception entry is created approved and traced end-to-end through the exception register
  - id: pt-060
    status: in-progress
    epic_id: epic-15
    sprint_id: sprint-23
    milestone_id: m15-3
    name: complete-quarterly-access-review-cycle-1-and-produce-compliance-declaration
    deliverable: privileged access review record cycle 1 plus data-governance-compliance-declaration as operational_declaration document approved by executive_sponsor
    verification: declaration is signed by executive_sponsor including confirmation that classification redaction access control and retention controls are all active and tested
  - id: pt-061
    status: in-progress
    epic_id: epic-16
    sprint_id: sprint-24
    milestone_id: m16-1
    name: execute-backup-restore-drill-cycle-2-and-compare-to-cycle-1
    deliverable: backup-restore-drill-evidence-cycle-2 with side-by-side comparison report showing regression status and any new findings
    verification: cycle-2 drill is executed by an operator different from cycle-1 where possible and the comparison shows no unaddressed regression
  - id: pt-062
    status: in-progress
    epic_id: epic-16
    sprint_id: sprint-24
    milestone_id: m16-1
    name: run-load-test-v2-and-produce-regression-comparison-report
    deliverable: load-test-results-v2 with explicit comparison to v1 p95 latency and throughput results and documented status for any degradation
    verification: all p95 latency budgets defined in epic-13 capacity model are met or have a documented remediation plan if exceeded
  - id: pt-063
    status: in-progress
    epic_id: epic-16
    sprint_id: sprint-24
    milestone_id: m16-1
    name: run-model-evaluation-harness-cycle-2-and-produce-regression-summary
    deliverable: model-evaluation-results-cycle-2 with regression summary comparing to cycle-1 results across all supported task types
    verification: no task type shows regression beyond tolerance without a documented finding and remediation owner
  - id: pt-064
    status: in-progress
    epic_id: epic-16
    sprint_id: sprint-24
    milestone_id: m16-2
    name: complete-privileged-access-review-cycle-2-and-record
    deliverable: privileged-access-review-record-cycle-2 documenting all privileged access changes detections and approvals since cycle-1
    verification: all privileged credentials on orchestrator postgres-main and hz.* nodes are accounted for and any undocumented access is raised as a finding
  - id: pt-065
    status: in-progress
    epic_id: epic-16
    sprint_id: sprint-24
    milestone_id: m16-2
    name: record-service-review-minutes-cycle-2-and-confirm-cadence-active
    deliverable: service-review-minutes-cycle-2 confirming that monthly service health reviews are running with documented outputs and open action items
    verification: at least two consecutive monthly review minutes exist with action item tracking and evidence that findings from cycle-1 were addressed or carried forward
  - id: pt-066
    status: in-progress
    epic_id: epic-16
    sprint_id: sprint-24
    milestone_id: m16-2
    name: execute-alert-response-drill-and-verify-runbooks-through-non-authors
    deliverable: alert-response-drill-record and runbook-execution-records-pack covering at least three runbooks executed by operators other than the original authors
    verification: drill record shows L1 to L2 escalation path was exercised with documented response times and no runbook step was found to be ambiguous or broken
  - id: pt-067
    status: in-progress
    epic_id: epic-16
    sprint_id: sprint-24
    milestone_id: m16-3
    name: verify-change-log-activity-baseline-and-approve-sustained-operation-declaration
    deliverable: governance change log showing at least 10 post-deployment operational entries plus sustained-operation-declaration as operational_declaration document approved by executive_sponsor
    verification: all second-cycle evidence artifacts are linked in the declaration, all recurring loops are confirmed as executed at minimum twice, and executive_sponsor has approved the document
program_to_effective_traceability:
  - program_epic_id: epic-0
    primary_effective_epic_ids: [impl-epic-1]
    supporting_effective_epic_ids: [impl-epic-8, impl-epic-10]
    rationale: governance rules bootstrap execution discipline and status controls are operationalized before and across all effective implementation work
  - program_epic_id: epic-1
    primary_effective_epic_ids: [impl-epic-3, impl-epic-9]
    supporting_effective_epic_ids: [impl-epic-7]
    rationale: canonical document contracts feed schema taxonomy pilot artifact packs and bounded retrieval inputs
  - program_epic_id: epic-2
    primary_effective_epic_ids: [impl-epic-3, impl-epic-4]
    supporting_effective_epic_ids: [impl-epic-6]
    rationale: registry schema taxonomy security boundaries and operational queryability define the system-of-record layer
  - program_epic_id: epic-3
    primary_effective_epic_ids: [impl-epic-5, impl-epic-6]
    supporting_effective_epic_ids: []
    rationale: approved discovery adapters backfill validation and reconciliation instantiate the observed-state pipeline against real infrastructure
  - program_epic_id: epic-4
    primary_effective_epic_ids: [impl-epic-7]
    supporting_effective_epic_ids: [impl-epic-9]
    rationale: context broker chunking embeddings and evidence-pack generation realize bounded deterministic-first retrieval for real work
  - program_epic_id: epic-5
    primary_effective_epic_ids: [impl-epic-8]
    supporting_effective_epic_ids: [impl-epic-9, impl-epic-10]
    rationale: mediated approvals prompt governance and agent audit create the controlled execution plane and its review surface
  - program_epic_id: epic-6
    primary_effective_epic_ids: [impl-epic-9]
    supporting_effective_epic_ids: [impl-epic-7, impl-epic-8]
    rationale: the pilot flow validates that retrieval governance approvals and verification artifacts can deliver a real bounded outcome end-to-end
  - program_epic_id: epic-7
    primary_effective_epic_ids: [impl-epic-10]
    supporting_effective_epic_ids: [impl-epic-5, impl-epic-6, impl-epic-7, impl-epic-8, impl-epic-9]
    milestone_traceability:
      - program_milestone_id: m7-1
        effective_milestone_ids: [impl-m17, impl-m18]
      - program_milestone_id: m7-2
        effective_milestone_ids: [impl-m17, impl-m18]
      - program_milestone_id: m7-3
        effective_milestone_ids: [impl-m18]
      - program_milestone_id: m7-4
        effective_milestone_ids: [impl-m19]
      - program_milestone_id: m7-5
        effective_milestone_ids: [impl-m20]
      - program_milestone_id: m7-6
        effective_milestone_ids: [impl-m21]
    sprint_traceability:
      - program_sprint_id: sprint-9
        effective_sprint_ids: [impl-sprint-10]
      - program_sprint_id: sprint-10
        effective_sprint_ids: [impl-sprint-10]
      - program_sprint_id: sprint-11
        effective_sprint_ids: [impl-sprint-10]
      - program_sprint_id: sprint-20
        effective_sprint_ids: [impl-sprint-11]
      - program_sprint_id: sprint-21
        effective_sprint_ids: [impl-sprint-12]
      - program_sprint_id: sprint-22
        effective_sprint_ids: [impl-sprint-13]
    task_traceability:
      - program_task_id: pt-022
        effective_task_ids: [impl-t-045, impl-t-046]
      - program_task_id: pt-023
        effective_task_ids: [impl-t-047, impl-t-048]
      - program_task_id: pt-024
        effective_task_ids: [impl-t-049]
      - program_task_id: pt-046
        effective_task_ids: [impl-t-050]
      - program_task_id: pt-047
        effective_task_ids: [impl-t-051]
      - program_task_id: pt-048
        effective_task_ids: [impl-t-052]
      - program_task_id: pt-049
        effective_task_ids: [impl-t-053]
      - program_task_id: pt-050
        effective_task_ids: [impl-t-054]
      - program_task_id: pt-051
        effective_task_ids: [impl-t-055]
      - program_task_id: pt-052
        effective_task_ids: [impl-t-056]
      - program_task_id: pt-053
        effective_task_ids: [impl-t-057]
      - program_task_id: pt-054
        effective_task_ids: [impl-t-058]
    rationale: observability retention runbooks and readiness review close the loop across registry discovery retrieval control-plane and pilot surfaces, so the primary delivery sits in impl-epic-10 while supporting evidence and observable behaviors come from the producing effective epics
  - program_epic_id: epic-8
    primary_effective_epic_ids: []
    supporting_effective_epic_ids: []
    rationale: this supplemental enterprise epic extends the current plan beyond wave-1 foundation and has no instantiated effective-track counterpart yet
  - program_epic_id: epic-9
    primary_effective_epic_ids: []
    supporting_effective_epic_ids: []
    rationale: this supplemental enterprise epic extends the current plan beyond wave-1 foundation and has no instantiated effective-track counterpart yet
  - program_epic_id: epic-10
    primary_effective_epic_ids: []
    supporting_effective_epic_ids: []
    rationale: this supplemental enterprise epic extends the current plan beyond wave-1 foundation and has no instantiated effective-track counterpart yet
  - program_epic_id: epic-11
    primary_effective_epic_ids: []
    supporting_effective_epic_ids: []
    rationale: this supplemental enterprise epic extends the current plan beyond wave-1 foundation and has no instantiated effective-track counterpart yet
  - program_epic_id: epic-12
    primary_effective_epic_ids: []
    supporting_effective_epic_ids: []
    rationale: this supplemental enterprise epic extends the current plan beyond wave-1 foundation and has no instantiated effective-track counterpart yet
  - program_epic_id: epic-13
    primary_effective_epic_ids: []
    supporting_effective_epic_ids: []
    rationale: this supplemental enterprise epic extends the current plan beyond wave-1 foundation and has no instantiated effective-track counterpart yet
  - program_epic_id: epic-14
    primary_effective_epic_ids: []
    supporting_effective_epic_ids: []
    rationale: this supplemental enterprise epic extends the current plan beyond wave-1 foundation and has no instantiated effective-track counterpart yet
  - program_epic_id: epic-15
    primary_effective_epic_ids: []
    supporting_effective_epic_ids: []
    rationale: data governance and compliance controls epic is defined and has program_tasks pt-055 through pt-060 but does not yet have an instantiated effective-track counterpart; the ingest-time redaction scanner from pt-056 is the first cross-cutting impl deliverable once epic-15 enters active execution
  - program_epic_id: epic-16
    primary_effective_epic_ids: []
    supporting_effective_epic_ids: []
    rationale: sustained operation proof epic is intentionally last and depends on second-cycle evidence from all preceding epics; it has program_tasks pt-061 through pt-067 but no effective-track counterpart until epics 8-15 have produced at least one completed operational cycle
```

## Content: Intent and Use of This Plan

Acest document este artefactul de executie al programului, nu blueprint-ul conceptual. Blueprint-ul defineste arhitectura tinta si principiile. Planul de fata defineste ordinea de implementare, responsabilitatile, intrarile, iesirile, criteriile de intrare si iesire, regulile pentru agenti si modul in care se verifica ca implementarea ramane curata, completa si fara presupuneri.

Acest plan trebuie folosit astfel:

- ca referinta program-level pentru ordonarea lucrului pe epics, milestones, sprints si tasks;
- ca document de handoff pentru agenti care implementeaza fiecare pachet de lucru;
- ca baza pentru aprobari, pentru review-uri de progres si pentru decizii de go or no-go;
- ca mecanism de control pentru a preveni derapajele de tip improvizatie, schimbari neauditabile sau extinderi premature de scope.
- in caz de suprapunere intre descrierea generica program-level si `effective_delivery_track`, sectiunea `effective_delivery_track` prevaleaza pentru sequencing, livrabile concrete si acceptanta operationala a instantei curente.

## Content: Mandatory Operating Rules for Agents

Orice agent care primeste un task derivat din acest plan trebuie sa respecte simultan regulile de mai jos.

1. Agentul nu completeaza golurile cu presupuneri. Daca lipsesc date canonice, lipsesc bindings, lipsesc ownership mappings sau lipseste aprobarea pentru scriere, rezultatul corect nu este improvizarea, ci raportarea gap-ului si blocarea executiei pe acel segment.
2. Agentul porneste intotdeauna de la context structurat. Pentru orice task, ordinea de context este: documente canonice relevante, entitati si relatii din registry, stare observata si provenienta ei, reguli de policy, apoi doar complementar retrieval lexical sau semantic.
3. Agentul nu trateaza semantic retrieval ca sursa de adevar. Rezultatele semantice sunt suport contextual. Adevarul operational si deciziile obligatorii vin din documente canonice aprobate, query-uri structurate din registry si observatii runtime cu provenienta.
4. Agentul nu executa scrieri direct. Orice operatie care modifica fisiere, infrastructura, configuratii, registry state sau resurse de runtime trebuie sa treaca prin action broker si prin chain-ul de aprobare aplicabil clasei de risc.
5. Agentul lasa urma de audit. Pentru fiecare run trebuie sa existe identificator de run, input scope, context pack folosit, dovezi extrase, decizii luate, aprobari primite, actiuni executate si verificari finale.
6. Agentul lucreaza pe scope minim suficient. Daca task-ul vizeaza un serviciu, un host, o aplicatie sau un pachet de documente, contextul trebuie restrans la acel scope. Nu se incarca documente sau entitati largi doar pentru siguranta.
7. Agentul verifica inainte sa construiasca. Daca exista deja active in repo care acopera partial o nevoie, agentul trebuie sa le reuseasca, sa le normalizeze sau sa le extinda disciplinat, nu sa dubleze functionalitatea.
8. Agentul separa faptele de interpretare. In orice output trebuie sa fie clar ce este fapt canonic, ce este fapt observat, ce este inferenta limitata si ce este recomandare.
9. Agentul nu inchide task-ul fara verificare. Fiecare livrabil trebuie validat fie prin teste automate, fie prin query-uri/controale de consistenta, fie prin review formal de owner, in functie de natura task-ului.
10. Agentul escaladeaza explicit conflictele. Daca starea canonica si starea observata intra in conflict, agentul nu alege arbitrar una dintre ele. Conflictul trebuie marcat, clasificat si escaladat conform politicii.
11. Planul este read-only pentru agentii de implementare in tot continutul sau. Singura modificare permisa este actualizarea campului YAML `status` de pe obiectele de executie din plan.
12. Toate obiectele YAML de executie pornesc cu `status: in-progress` si pot fi schimbate in `completed` doar dupa implementarea efectiva 100% corecta si 100% completa a obiectului respectiv, urmata de o verificare critica foarte aprofundata pentru identificarea gap-urilor de implementare neacoperite.
13. Agentul de implementare nu are voie sa scrie, sa rescrie sau sa completeze alt text in plan, nu are voie sa modifice acceptanta, sequencing-ul, descrierile sau scope-ul; singura exceptie admisa este schimbarea valorii campului `status` din `in-progress` in `completed` atunci cand criteriul de mai sus este satisfacut integral.

## Content: Program Execution Model

Modelul de executie este secvential in dependinte, dar paralelizabil in interiorul etapelor care nu isi invalideaza reciproc rezultatele. Regulile de ordonare sunt:

- governance si ADR-urile blocheaza tot ce presupune alegeri structurale persistente;
- taxonomy si metadata blocheaza template packs, registry bindings si retrieval contracts;
- schema registry blocheaza ingestia, query contracts si reconciliation-ul;
- deterministic retrieval blocheaza semantic augmentation si policy-constrained context brokering;
- policy matrix si action contracts blocheaza orice write-path operationalizat;
- pilotul nu valideaza platforma daca este executat cu bypass-uri manuale neauditate;
- rollout-ul nu porneste pana cand KPI-urile, auditul si runbook-urile operationale nu sunt active.

## Content: What Clean Implementation Means in This Program

Implementare curata si completa inseamna urmatoarele:

- fiecare strat arhitectural are contracte explicite, nu dependinte implicite intre componente;
- fiecare entitate si document important are identificatori stabili, ownership si provenienta;
- registry-ul nu devine un depozit generic de JSON fara semantica si fara constrangeri;
- retrieval-ul nu este un chat peste documente, ci un mecanism disciplinat de context assembly;
- control plane-ul nu este doar observabil, ci si restrictiv: poate bloca, aproba, inregistra si explica;
- pilotul valideaza realmente fluxul guvernat, nu doar capacitatea unei echipe de a depasi manual limitarile platformei;
- toate rezultatele cheie sunt reproductibile si auditabile.

## Content: Detailed Execution Guidance by Epic

### Epic 0: Program Foundations and Governance

Scopul acestui epic este sa elimine ambiguitatea structurala. Niciun agent nu trebuie sa inceapa design de schema, design de retrieval sau fluxuri de executie pana cand deciziile de baza nu sunt formulate in limbaj de decizie, nu doar in limbaj narativ.

Intrari obligatorii:

- blueprint-ul complet;
- inventarul activelor existente din repo;
- lista intrebarilor arhitecturale deschise;
- decizia confirmata ca abordarea este enterprise-first, cu embeddings locale si cu aprobare pentru orice scriere.

Iesiri obligatorii:

- set de ADR-uri scurte si neambigue;
- matrice de ownership pe roluri;
- model de aprobare si escaladare;
- regula de gestionare a conflictelor canonical vs observed.

Instrucțiuni pentru agenti:

- nu rescrie blueprint-ul; extrage deciziile care trebuie inghetate in ADR-uri;
- nu atribui nume de persoane daca nu exista; foloseste roluri si marcheaza explicit ca rolurile trebuie numite de sponsor;
- daca gasesti decizii contradictorii intre documente, nu alege singur; emite conflict record;
- fiecare ADR trebuie sa includa motivatia, alternativa respinsa si impactul asupra epics-urilor dependente.

Criteriu real de terminare:

- un alt agent poate incepe epic-1 si epic-2 fara sa reinventeze regulile de adevar, ownership sau aprobare.

### Epic 1: Canonical Sources and Document Governance

Acest epic transforma documentatia din continut liber in suprafata executabila. Fara el, nici registry-ul, nici retrieval-ul nu au o baza disciplinata.

Ce trebuie produs in mod concret:

- clase de documente pentru infrastructura, shared services, aplicatii, governance, runbooks si policies;
- frontmatter standardizat pentru ownership, status, identifiers, relations, dependencies, approval state, provenance bindings;
- conventii de naming si linking care permit traversarea determinista;
- template packs minimale dar suficiente pentru adoptie operationala.

Instrucțiuni pentru agenti:

- proiecteaza taxonomia pentru utilitate operationala, nu pentru eleganta teoretica;
- fiecare camp din metadata schema trebuie justificat printr-un consumer real: registry binding, retrieval filter, governance review, reconciliation sau audit;
- evita template-urile gigantice; defineste mandatory, recommended si optional fields distinct;
- valideaza pe documente reale din wave-1, nu doar pe exemple artificiale.

Erori de evitat:

- crearea unei taxonomii prea fine care obliga documente greu de mentinut;
- lipsa unui identifier stabil per document si per entity binding;
- campuri de metadata care nu pot fi validate automat;
- template-uri care descriu prea putin pentru runtime dependencies si operational ownership.

Criteriu real de terminare:

- orice document nou din wave-1 poate fi creat, validat, legat in registry si interogat de retrieval fara interpretari ad-hoc.

### Epic 2: Operational Registry and Data Model

Acesta este nucleul operational al programului. Scopul sau nu este sa mute adevarul din Git in baza de date, ci sa creeze un model queryable, coerent si auditabil al entitatilor, relatiilor si starilor relevante.

Ce trebuie modelat explicit:

- identitatea entitatilor infrastructurale si aplicative;
- relatii structurale si dependinte operationale;
- separarea starilor canonice, observate si dorite;
- provenance, confidence si lifecycle;
- legatura dintre documente canonice si entitati registry.

Instrucțiuni pentru agenti:

- nu accepta tabele generice care muta toata semantica in JSONB daca relatia este stabila si importanta;
- foloseste JSONB pentru extensibilitate, nu pentru a evita modelarea;
- defineste clar cheile naturale si cheile surrogate acolo unde este necesar;
- proiecteaza query contracts pentru task-urile cunoscute: lookup de host, mapare de dependinte, extragere de ownership, compunere context pack;
- include de la inceput coloane si structuri pentru provenienta si timestamps de observatie, nu ca post-scriptum.

Verificari obligatorii:

- schema review pe exemple reale din clusterul curent;
- validarea faptului ca acelasi model suporta extindere la mai multe clustere;
- verificarea faptului ca observatiile runtime nu pot suprascrie fara control definitiile canonice.

Criteriu real de terminare:

- query-urile esentiale pentru retrieval, reconciliation si audit se pot formula fara logica ascunsa in cod procedural excesiv.

### Epic 3: Discovery, Ingestion and Reconciliation

Acest epic conecteaza platforma la realitatea infrastructurii. Fara el, platforma ramane o documentatie frumoasa dar oarba operational.

Ce trebuie produs:

- contracte de colectare pe surse prioritare;
- reguli de normalizare si mapping la entitati registry;
- reguli de confidence si provenance;
- jobs de ingestie repetabile;
- model de drift si severity.

Instrucțiuni pentru agenti:

- trateaza scripturile existente de audit ca material de analiza si reutilizare, nu ca arhitectura finala;
- normalizeaza denumiri, enum-uri, unitati de masura si identificatori inainte de persistenta;
- capteaza provenance la nivel suficient: sursa, timestamp, collector version, host sau endpoint, eventual command fingerprint;
- marcheaza explicit datele partiale, neconfirmate sau conflictuale;
- pentru drift, separa mismatches informative de mismatches care trebuie sa blocheze change flows.

Verificari obligatorii:

- sample ingestion pe surse reale din clusterul curent;
- cazuri de drift simulate si reale;
- freshness measurements pentru fiecare collector relevant;
- audit review pe modul in care provenance este pastrat end-to-end.

Criteriu real de terminare:

- platforma poate spune cu evidenta ce crede despre starea curenta, de unde stie acel lucru si cat de proaspata este informatia.

### Epic 4: Retrieval and Evidence Brokerage

Acesta este mecanismul prin care agentii primesc context util fara sa fie supra-alimentati cu documente brute. Este esential ca retrieval-ul sa fie intai determinist, apoi semantic, si intotdeauna bounded.

Ce trebuie produs:

- catalog de task types suportate;
- contracte de evidence pack per task type;
- query-uri structurate si lexical search pe subseturi aprobate;
- embeddings locale, chunking si ranking pentru completare semantica;
- politici de token budget si truncation.

Instrucțiuni pentru agenti:

- defineste task types pornind de la lucrari reale: analiza infrastructura, modificare config, definire aplicatie, troubleshooting bounded, deploy controlat;
- pentru fiecare task type, specifica exact ce dovezi sunt mandatory, recommended si disallowed;
- in evidence pack, separa clar facts, constraints, unresolved gaps, candidate references si approval state;
- semantic retrieval nu are voie sa schimbe ordinea de incredere: registry facts si documentele canonice aprobate raman pe primul plan;
- proiecteaza pachete compacte, cu rationale de includere pentru fiecare componenta de context.

Verificari obligatorii:

- testare pe task-uri reale din wave-1;
- comparatie intre context pack mare si context pack bounded pentru calitate si cost;
- verificarea faptului ca provenance links se pastreaza pana in outputul folosit de agent.

Criteriu real de terminare:

- un agent poate executa un task suportat folosind un context pack mic, justificat si complet din punct de vedere al constrangerilor critice.

### Epic 5: Agent Control Plane, Policy and Approvals

Acesta este stratul care transforma platforma din knowledge system intr-un execution system sigur. Fara el, agentii ar avea prea multa libertate si prea putina trasabilitate.

Ce trebuie produs:

- task class policy matrix;
- clasificare de tool-uri si actiuni pe risc;
- action contracts si approval workflow;
- retrieval broker si action broker;
- run audit model.

Instrucțiuni pentru agenti:

- clasifica task-urile in functie de impact: read-only analysis, bounded write to repo, bounded runtime change, high-risk infrastructure change;
- pentru fiecare clasa, defineste clar ce tool-uri sunt permise, ce approvals sunt necesare, ce evidence este mandatory si ce verificare post-executie este obligatorie;
- nu lasa niciun write path in afara action broker-ului, nici macar pentru convenience operational;
- orice aprobare trebuie sa fie legata de input scope, intent, risc, schimbari propuse si expirare;
- auditul de run trebuie sa poata raspunde ulterior la intrebarea: cine a cerut, ce context a fost folosit, ce reguli s-au aplicat, ce s-a schimbat si cum s-a verificat.

Verificari obligatorii:

- teste pentru deny paths si expired approvals;
- teste pentru audit completeness;
- demonstratie ca read-only discovery poate rula fara aprobare dar cu audit complet;
- demonstratie ca write actions sunt blocate in absenta aprobarii corespunzatoare.

Criteriu real de terminare:

- un agent nu mai poate executa operatii suportate in afara unui cadru controlat, auditat si aprobat.

### Epic 6: Delivery Control and Pilot Application Flow

Acest epic trebuie sa dovedeasca faptul ca platforma produce valoare practica. Pilotul nu este demo; este validarea ca definitiile, retrieval-ul, politicile si broker-ele pot livra o aplicatie noua intr-un flux disciplinat.

Ce trebuie produs:

- selectie de pilot bounded;
- application definition pack complet;
- maparea dependintelor catre shared services si infrastructura;
- rulare end-to-end a fluxului guvernat;
- dovada de repetabilitate.

Instrucțiuni pentru agenti:

- alege pilotul pentru valoare de validare, nu pentru prestigiu sau complexitate maxima;
- pack-ul aplicatiei trebuie sa includa runtime requirements, dependencies, ownership, operational checks, rollback expectations si acceptance rules;
- orice pas manual ramas trebuie declarat ca gap al platformei, nu mascat;
- comparatia dintre prima rulare si a doua rulare este obligatorie pentru a detecta dependinte ascunse sau drift de mediu.

Verificari obligatorii:

- aprobarea pachetului aplicatiei de catre owner-ul de domeniu;
- audit complet al intregului flux;
- raport de delta intre prima si a doua rulare;
- verificare functionala post-deploy si verificare a contractelor dependente.

Criteriu real de terminare:

- platforma poate produce si verifica repetabil un rezultat end-to-end pe un caz real, fara improvizatii ascunse.

### Epic 7: Observability, Audit, Retention and Rollout

Acest epic inchide bucla operationala. Fara el, programul nu poate spune daca platforma este sanatoasa, daca politicile sunt respectate si daca este sigur sa scaleze catre alte domenii.

Grafana shared de pe `orchestrator` este suprafata operationala potrivita pentru dashboard-uri, consum de alerte si vizibilitate comuna de operare, dar nu trebuie tratata ca sursa canonica unica pentru definitiile de KPI/SLO, retention sau runbooks. Acestea trebuie sa ramana versionate si aprobate in plan, Git si politicile asociate, apoi proiectate disciplinat in suprafetele shared de observabilitate.

Ce trebuie produs:

- contract aprobat de semnale pentru metrics, logs, audit events si health queries derivate;
- set de KPI-uri si SLO-uri;
- dashboards shared in Grafana si alerting cu routing si escaladare testate;
- politici de retention si acces la audit;
- runbooks operationale legate direct din dashboard-uri si alerte;
- exercitii de observabilitate pentru failure modes relevante;
- readiness review si criterii de wave-2.

Instrucțiuni pentru agenti:

- nu considera complet un dashboard daca nu are owner, semnal sursa clar, praguri utile si legatura catre raspuns operational;
- trateaza contractele de semnal ca parte a produsului, nu ca detaliu de implementare lasat la latitudinea echipelor;
- defineste KPI-uri care ajuta decizii, nu doar raportare decorativa;
- leaga fiecare alert important de un runbook;
- retention-ul trebuie sa acopere atat nevoia de audit, cat si costurile si sensibilitatea datelor;
- foloseste Grafana shared ca suprafata operationala comuna, dar mentine sursa canonica a definitiilor in artefactele guvernate;
- readiness review trebuie sa fie bazat pe evidenta acumulata, nu pe optimism privind urmatorul val.

Verificari obligatorii:

- inventar aprobat de semnale si owneri pentru suprafetele critice din wave-1;
- exercitii de alerting pe failure modes relevante;
- testare a routing-ului si escaladarii pentru alertele critice, nu doar randare de dashboard-uri;
- sample reviews de audit trails;
- validarea retention-ului pe suprafete reale de colectare, audit si evidenta;
- validarea faptului ca high-severity gaps au owner si termen;
- gate review formal pentru extindere.

Criteriu real de terminare:

- exista o baza defensibila pentru decizia de a extinde platforma fara a-i rupe disciplina operationala, iar suprafata shared de observabilitate demonstreaza operabilitate reala, nu doar intentie documentata.

### Epic 8: Business Continuity, Backup, Restore and Disaster Recovery

Acest epic transforma persistenta si backup-ul din presupunere operationala in capacitate verificata de recuperare. Fara el, existenta unor directoare de backup sau a unui volum persistent nu demonstreaza ca platforma poate reveni controlat dupa eroare, corupere sau pierdere de host.

Ce trebuie produs:

- obiective aprobate de RTO si RPO;
- postura explicita HA versus single-instance tolerated pentru `internalCMDB`;
- proceduri de backup si restore pentru baza de date si artefactele critice de audit;
- runbooks de disaster response si disaster simulation;
- registru de remedieri rezultate din exercitii de recuperare.

Instrucțiuni pentru agenti:

- nu confunda existenta `backup_path` cu dovada de recoverability;
- trateaza datele registry si artefactele de audit ca suprafete de recuperare diferite, cu cerinte diferite de validare;
- declara explicit daca postura aprobata este single-instance acceptata sau daca exista cerinta de HA; nu lasa aceasta decizie implicita;
- orice exercitiu de restore trebuie sa verifice nu doar revenirea procesului, ci si integritatea datelor, a migrarilor si a suprafetelor minime de query.

Verificari obligatorii:

- aprobare explicita pentru RTO/RPO si pentru postura de disponibilitate;
- backup testat cu restore efectiv intr-un context controlat;
- exercitiu de disaster simulation cu findings documentate;
- verificare ca runbooks de recovery sunt suficient de clare pentru a fi executate fara cunoastere tacita.

Criteriu real de terminare:

- platforma poate demonstra cu evidenta ca isi poate recupera datele si artefactele critice in postura aprobata, nu doar ca le poate copia undeva.

### Epic 9: Secrets, PKI and Trust Management

Acest epic inchide partea de incredere si credentiale. Fara el, control plane-ul si accesul la runtime raman vulnerabile la exceptii prelungite, credentiale netransparente si trust model implicit.

Ce trebuie produs:

- model aprobat de secret storage si boundary de acces;
- separare de roluri pentru credentiale privilegiate;
- rotatie a credentialelor bootstrap si reducerea exceptiilor temporare;
- lifecycle complet pentru certificate, trust anchors si recuperare dupa expirare sau compromitere;
- audit trail pentru accesul privilegiat la secrete si materiale de incredere.

Instrucțiuni pentru agenti:

- nu pastra postura `temporary-no-password-exception` mai mult decat este aprobat explicit;
- trateaza certificatele si cheile private ca artefacte guvernate, nu ca simple fisiere de configuratie;
- nu propune secret handling nou in afara boundary-ului aprobat doar pentru convenience operational;
- orice rotatie trebuie sa includa impact analysis pe serviciile dependente si cale de recovery in caz de esec.

Verificari obligatorii:

- review de access boundary pentru fiecare clasa de secret critic;
- dovada ca bootstrap credentials au fost eliminate sau constrainse;
- testare pentru renewal sau replacement pe cel putin un flux TLS relevant;
- verificare ca accesul privilegiat lasa urme de audit suficiente pentru review ulterior.

Criteriu real de terminare:

- accesul privilegiat si increderea TLS nu mai depind de exceptii tacite, ci de un model explicit, rotabil si auditabil.

### Epic 10: Supply Chain Security and Release Integrity

Acest epic controleaza integritatea componentelor software care intra in platforma. Fara el, runtime-ul poate fi corect functional dar indefensabil din punct de vedere al provenientei, licentierii si riscului third-party.

Ce trebuie produs:

- inventar de dependinte, imagini si surse third-party;
- SBOM baseline pentru componentele principale;
- dependency scanning si image scanning cu gates reviewable;
- policy pentru provenance, signing sau attestation;
- baseline de license review pentru artefactele promovate.

Instrucțiuni pentru agenti:

- nu limita integritatea supply chain doar la imagini container; include si toolchain-ul Python, librariile si artefactele de build;
- orice dependency critic neinventariat trebuie tratat ca gap, nu ca detaliu de implementare ulterior;
- nu promova artefacte ca fiind curate daca rezultatele de scanare nu sunt evaluate conform unei politici explicite;
- provenance trebuie sa lege artefactul de sursa si de decizia de promovare, nu doar de build-ul local.

Verificari obligatorii:

- inventar review pentru componentele si dependintele majore;
- scanari efective cu rezultate pastrate pentru audit;
- policy review pentru attestation sau signing;
- verificare ca release artifacts promovate pot fi urmarite pana la sursa si evaluarea lor de risc.

Criteriu real de terminare:

- platforma poate demonstra de unde provin artefactele sale principale, ce risc software cunoscut au si de ce au fost acceptate in runtime.

### Epic 11: Environment Promotion and Release Management

Acest epic standardizeaza trecerea schimbarilor intre medii si clase de release. Fara el, aprobarea si rollback-ul raman dependente de conventii locale si de memorie umana, nu de un contract operational clar.

Ce trebuie produs:

- model aprobat de environment classes si promotion gates;
- release approval matrix pe clase de schimbare;
- rollback contracts si migration recovery playbooks;
- lant de evidenta pentru release de la artifact integrity la post-release verification;
- reguli pentru go, hold si rollback in functie de semnalul operational.

Instrucțiuni pentru agenti:

- nu presupune existenta unui traseu clasic dev-test-prod daca modelul real de medii este diferit; documenteaza ce exista cu adevarat;
- trateaza migrarile bazei de date ca schimbari cu contract de rollback sau recovery explicit, nu ca simple deploy-uri de cod;
- promotion gate-urile trebuie sa fie corelate cu clasa de risc si cu suprafata afectata;
- post-release verification trebuie sa fie parte din release contract, nu activitate optionala dupa deploy.

Verificari obligatorii:

- review al claselor de environment si al gates-urilor de promovare;
- drill sau simulare pentru migration recovery si rollback;
- verificare ca orice release promovat are evidence chain complet;
- verificare ca deciziile de release sunt reconstructibile pentru audit sau incident review.

Criteriu real de terminare:

- schimbarile pot fi promovate, blocate sau retrase printr-un model explicit si auditabil, nu prin bune intentii locale.

### Epic 12: LLM Runtime, Model Registry and Evaluation Governance

Acest epic inchide operational partea de runtime pentru modelele self-hosted folosite de agenti. Fara el, control plane-ul si retrieval-ul pot exista, dar selectia, rutarea si evaluarea modelelor raman prea informale pentru o platforma enterprise disciplinata.

Ce trebuie produs:

- model serving stack aprobat pentru clasele relevante de modele;
- model registry si policy de activare/dezactivare a modelelor;
- routing rules si fallback strategy pe task type sau task class;
- evaluation harness si benchmark set intern pe taskuri suportate;
- guardrails de latenta, cost si safety pentru comportamentul runtime.

Instrucțiuni pentru agenti:

- nu trata modelul activ ca detaliu de infrastructura interschimbabil fara impact asupra rezultatului; model choice este parte din governance;
- benchmark-urile trebuie sa fie legate de task types aprobate, nu de exemple arbitrare convenabile;
- fallback-ul trebuie sa degradeze controlat, nu sa schimbe tăcut semantica taskului sau nivelul de siguranta;
- orice red-team sau safety check trebuie sa fie legat de suprafetele reale de risc ale agentilor, nu doar de benchmark-uri generice de laborator.

Verificari obligatorii:

- review pentru model registry si routing policy;
- rulare repetabila a evaluation harness pe task types suportate;
- verificare pentru fallback behavior sub esec, overload sau cost pressure;
- validare ca guardrails de safety si cost sunt aplicabile operational, nu doar declarative.

Criteriu real de terminare:

- platforma poate justifica ce modele ruleaza, pentru ce taskuri, pe baza caror evaluari si cum se comporta sub esec sau degradare.

### Epic 13: Capacity, Performance and Resilience Engineering

Acest epic cuantifica limitele platformei. Fara el, scale-out-ul, wave-2 si claims despre readiness raman nefundamentate in date de performanta, cost si comportament la esec.

Ce trebuie produs:

- model de capacitate pentru PostgreSQL, vector storage si brokeri;
- baseline de cost si crestere a datelor;
- load tests si stress tests pentru suprafetele critice;
- reguli explicite de fail-open versus fail-closed;
- registru de remedieri pentru problemele de performanta si rezilienta descoperite.

Instrucțiuni pentru agenti:

- nu reduce capacity planning la CPU si RAM; include cresterea de date, query patterns, embeddings si concurenta pe brokeri;
- foloseste failure modes relevante pentru infrastructura reala, nu scenarii exotice fara legatura cu clusterul curent;
- orice prag de performanta sau latenta trebuie corelat cu task types si cu suprafetele pe care utilizatorii sau operatorii chiar le consuma;
- daca un test arata comportament periculos, acesta trebuie documentat ca risc activ, nu relativizat prin comparatie cu asteptari neformalizate.

Verificari obligatorii:

- review pentru modelul de capacitate si cost;
- load si stress tests pe suprafetele critice ale registry-ului si brokerilor;
- exercitii de failure injection sau simulare de degradare;
- verificare ca rezultatele sunt traduse in reguli operationale, nu doar intr-un raport uitat.

Criteriu real de terminare:

- platforma are limite de capacitate, performanta si comportament la esec cunoscute, masurate si folosite in deciziile de operare si extindere.

### Epic 14: Support Model, RACI Finalization and Service Operations

Acest epic finalizeaza trecerea de la roluri abstracte la model operational uman complet. Fara el, chiar o platforma tehnic bine construita ramane greu de operat coerent in incident, review sau change governance.

Ce trebuie produs:

- RACI numit pe servicii, capabilitati si review loops;
- model L1/L2/L3 si reguli de on-call si escaladare;
- incident command baseline pentru incidentele critice;
- cadence-uri obligatorii pentru service review, incident review si privileged access review;
- boundaries clare intre ownership tehnic, ownership de policy si ownership de domeniu.

Instrucțiuni pentru agenti:

- nu trata rolurile definite in plan ca inlocuitor pentru persoane sau grupuri reale; ele sunt doar scheletul guvernantei;
- support model-ul trebuie legat de criticitatea serviciilor si de deny paths, nu doar de organigrama;
- recurring reviews trebuie sa aiba owner, frecventa, input obligatoriu si output actionabil;
- orice zona fara owner numit trebuie marcata ca risc operational, nu lasata in zona de bun-simt organizational.

Verificari obligatorii:

- review si aprobare pentru RACI numit;
- testare sau simulare a traseului de escaladare si on-call pe un scenariu critic;
- verificare ca recurring reviews sunt programate si au inputs definite;
- verificare ca privileged access review este integrat in modelul operational si de risc.

Criteriu real de terminare:

- platforma are un model uman de operare si raspundere suficient de clar incat incidentele, review-urile si schimbarile sa nu depinda de memorie institutionala informala.

## Content: Program-Level Context and Agent Guidance by Epic

### Program Context for Epic 0: Program Foundations and Governance

Ancore reale de context si evidenta:

- blueprint-ul din `docs/blueprint_platforma_interna.md` ramane sursa arhitecturala primara;
- planul curent codifica deja regulile audit-first, anti-hallucination, status governance si read-only discipline pentru agentii de implementare;
- repo-ul activ si branch-ul de lucru exista deja, iar executia wave-1 se desfasoara pe baza activelor reale deja prezente in workspace;
- deciziile deja validate pentru aceasta instanta includ distinctia explicita dintre doua suprafete PostgreSQL cu rol diferit: `postgres-main`, host existent si reachable care ruleaza `postgresql@18-main.service` pentru aplicatii, si runtime-ul dedicat `internalCMDB` planificat containerizat pe `orchestrator`, cu persistenta pe `/mnt/HC_Volume_105014654` si expunere tinta separata prin `postgres.orchestrator.neanelu.ro:5432` via Traefik TCP/SNI; la auditul de trust din 2026-03-08 ambele endpoint-uri publice `postgres.neanelu.ro:5432` si `postgres.orchestrator.neanelu.ro:5432` au raspuns cu `connection refused`, deci distinctia de rol este valida, dar expunerea publica efectiva pe `:5432` ramane de validat operational.

Riscuri critice de continut inca deschise:

- rolurile sunt definite corect la nivel de plan, dar nu sunt inca numite formal prin persoane sau grupuri reale;
- setul de ADR-uri este implicit in plan, dar nu exista inca extras in artefacte ADR separate versionate;
- modelul de exception handling este descris corect, dar nu este inca demonstrat prin cazuri reale de conflict canonical-versus-observed.

Context pentru milestone-uri:

- m0-1 inseamna congelarea bazei decizionale minime fara de care toate epicele urmatoare risca sa isi inventeze reguli locale;
- m0-2 inseamna operationalizarea disciplinei de executie, astfel incat orice handoff catre agenti sa poata fi evaluat dupa aceleasi reguli de adevar, verificare si inchidere.

Context pentru sprinturi:

- sprint-1 trebuie tratat ca sprint de guvernanta executabila, nu ca sprint de implementare tehnica;
- sprint-2 trebuie tratat ca sprint de stabilizare a regulilor de delivery, pentru a bloca proliferarea de exceptii locale in epicele tehnice.

Context pentru taskuri si handoff catre agenti:

- pt-001 cere extragerea stricta a deciziilor deja sustinute de blueprint si de observatiile live deja validate, fara rescriere creativa a intentiei arhitecturale;
- pt-002 cere matrice de ownership pe roluri reale de program, nu alias-uri tehnice ad-hoc si nu presupuneri despre cine aproba implicit;
- pt-003 cere transformarea regulilor deja scrise in plan in disciplina executabila pentru taskuri, handoff, verificare si promovarea statusurilor.

### Program Context for Epic 1: Canonical Sources and Document Governance

Ancore reale de context si evidenta:

- repo-ul contine deja artefactele canonice relevante pentru wave-1, in special `docs/blueprint_platforma_interna.md`, acest plan, `README.md`, `pyproject.toml`, `src/proiecteit/__main__.py`, `src/proiecteit/health.py` si testele existente;
- directia declarata si deja aprobata in plan este ca adevarul canonic ramane in Git, nu intr-un document system of record separat;
- pachetul minim de documente obligatorii pentru pilot este deja fixat: research dossier, application definition pack, verification specification si evidence map.

Riscuri critice de continut inca deschise:

- taxonomy si metadata schema sunt descrise si directionate, dar nu exista inca fisiere reale de template pack publicate in repo;
- nu exista inca un set demonstrat de documente wave-1 migrate complet pe noul contract de frontmatter;
- binding-ul document-la-entitate este definit conceptual, dar trebuie validat pe exemple reale de infrastructura si servicii deja auditate.

Context pentru milestone-uri:

- m1-1 trebuie sa produca exact campurile si regulile fara de care registry-ul si retrieval-ul nu pot filtra sau lega corect documentele;
- m1-2 trebuie sa transforme schema de metadata in suprafata utilizabila de autori si revieweri, nu doar in contract teoretic.

Context pentru sprinturi:

- sprint-1 trebuie sa stabileasca taxonomia si identificatorii stabili inainte de orice volum mare de authoring;
- sprint-2 trebuie sa demonstreze utilizabilitatea contractului prin template-uri si reguli de validare executabile.

Context pentru taskuri si handoff catre agenti:

- pt-004 cere definirea claselor de documente plecand de la ce exista deja in repo si din blueprint, nu de la o taxonomie generica copiata din alte platforme;
- pt-005 cere schema de metadata si conventii de linking care sa poata fi validate automat si consumate de registry si retrieval;
- pt-006 cere template pack real, guidance de adoptie si dovada ca un document nou wave-1 poate fi creat si aprobat fara coaching informal.

### Program Context for Epic 2: Operational Registry and Data Model

Ancore reale de context si evidenta:

- planul contine deja contractul extins de schema wave-1 pentru registry, retrieval si control plane in sectiunile de schema detaliata din partea a doua a documentului;
- decizia operationala pentru system of record este deja fixata: PostgreSQL containerizat pe `orchestrator`, cu runtime dedicat `internalCMDB`;
- observatiile live deja validate includ Docker root mutat pe `/mnt/HC_Volume_105014654/docker`, inexistenta unui PostgreSQL dedicat anterior pentru acest scop si topologia Proxmox reala: clusterul cu `orchestrator`, `hz.215`, `hz.223`, `hz.247`, plus instantele standalone `hz.118` si `hz.157`;
- modelarea explicita pentru `proxmox_cluster`, `proxmox_cluster_member` si `standalone_proxmox_host` este deja introdusa in plan pentru a reflecta infrastructura reala, nu o abstractie presupusa.

Riscuri critice de continut inca deschise:

- schema este foarte detaliata, dar nu exista inca dovada de rulare a lantului de migrari pe baza reala `internalCMDB`;
- politica exacta de versiune pentru extensii precum `pgvector` trebuie validata la momentul instalarii, nu doar asumata din blueprint;
- query contracts sunt descrise functional, dar nu exista inca un pachet real de query-uri aprobate ca suprafata operationala minima.

Context pentru milestone-uri:

- m2-1 trebuie sa fixeze modelul logic astfel incat entitatile si relatiile reale din clusterul curent sa poata fi reprezentate fara ambiguitati si fara pseudo-entitati;
- m2-2 trebuie sa transforme modelul logic in schema fizica si contracte de interogare care sustin retrieval, reconciliation si audit;
- m2-3 trebuie sa faca schema reproductibila si reviewable prin migrari, seed-uri si dictionar de date.

Context pentru sprinturi:

- sprint-2 inchide partea de model logic si trebuie sa consume direct blueprint-ul si auditul live deja facut;
- sprint-3 este sprintul in care teoria devine baza de date reala si contract de query, fara a muta semantica critica in JSONB generic;
- sprint-4 trebuie sa lase schema suficient de stabila pentru ca epicul de discovery sa construiasca loadere reale peste ea.

Context pentru taskuri si handoff catre agenti:

- pt-007 cere modelare stricta pe entitatile reale in scope: hosts, clustere, servicii, aplicatii, relatii de ownership, dovezi si stari;
- pt-008 cere schema fizica si query contracts astfel incat taskurile de lookup, retrieval si reconciliation sa nu depinda de logica ascunsa in cod procedural;
- pt-009 cere migrari reale, seed-uri de taxonomie si dictionar de date astfel incat implementatorii si reviewerii sa poata inspecta semantic schema fara interpretari paralele.

### Program Context for Epic 3: Discovery, Ingestion and Reconciliation

Ancore reale de context si evidenta:

- repo-ul contine deja surse reale de audit read-only care trebuie refolosite disciplinat: `subprojects/cluster-full-audit/audit_full.py`, `subprojects/cluster-audit/audit_cluster.py`, `subprojects/cluster-ssh-checker/test_cluster_ssh.py` si `scripts/test_cluster_ssh.py`;
- auditul live deja efectuat a confirmat acces read-only relevant in cluster si a produs informatii concrete despre topologia Proxmox si despre runtime-ul `orchestrator`;
- planul cere explicit separarea dintre starea observata, starea canonica si starea dorita, ceea ce face provenance-ul obligatoriu la nivel de load batch si de record.

Riscuri critice de continut inca deschise:

- nu toate sursele wave-1 au inca definite valori numerice pentru freshness si severity, deci semnalul operational risc-sa-fie-neuniform daca nu se inchide aceasta parte;
- scripturile existente au valoare de pornire, dar nu sunt inca demonstrat normalizate la contractele enterprise-grade ale registry-ului;
- exista risc de acoperire partiala daca anumite servicii sau hosturi sunt reachable doar intermitent si acest fapt nu este modelat explicit in ingestie.

Context pentru milestone-uri:

- m3-1 cere inventar prioritizat de surse si mapping explicit spre schema, nu doar lista de scripturi existente;
- m3-2 cere transformarea acestor surse in producatori si loadere repetabile, cu provenance end-to-end;
- m3-3 cere primul baseline complet de reconciliere, adica punctul in care platforma poate explica ce a observat, de unde si cat de proaspat este.

Context pentru sprinturi:

- sprint-4 este sprintul in care se inchid contractele de colectare si se porneste ingestia reala pe subsetul prioritar;
- sprint-5 este sprintul in care trebuie validate incarcarea completa, drift-ul si claritatea gap-urilor dintre plan si runtime;
- sprint-6 este consumatorul natural al rezultatelor de reconciliere pentru operational sign-off in track-ul efectiv.

Context pentru taskuri si handoff catre agenti:

- pt-010 cere inventariere bazata pe sursele deja existente si pe accesul read-only real, nu pe ideea teoretica a tuturor surselor posibile;
- pt-011 cere normalizare si loadere care sa poata fi rerulate fara reparatii manuale si fara pierderea provenientei;
- pt-012 cere prima incarcare completa si raportul de reconciliere care trebuie sa evidentieze si conflictele, si necunoscutele, nu doar succesele.

### Program Context for Epic 4: Retrieval and Evidence Brokerage

Ancore reale de context si evidenta:

- blueprint-ul si planul curent fixeaza deja ordinea obligatorie: context structurat din documente canonice si registry inainte de lexical si semantic retrieval;
- schema wave-1 contine deja obiectele necesare pentru `document_chunk`, `chunk_embedding`, `evidence_pack` si `evidence_pack_item`, ceea ce ofera o baza de date clara pentru implementare;
- strategia aprobata este embeddings locale, vector storage in PostgreSQL si bounded context packs, nu semantic search global nefiltrat.

Riscuri critice de continut inca deschise:

- setul exact de task types suportate in wave-1 nu este inca nominalizat intr-o lista operationala aprobata;
- modelul de embedding local este decis ca strategie, dar nu este inca pin-uit la o versiune sau la o selectie operationala specifica;
- bugetele reale de token si regulile concrete de truncare nu sunt inca parametrizate pe task type, ceea ce poate genera variatie in calitatea contextului.

Context pentru milestone-uri:

- m4-1 trebuie sa defineasca exact pentru ce tipuri de taskuri exista suport si ce dovezi intra sau nu intra in evidence packs;
- m4-2 trebuie sa demonstreze ordinea determinista si bounded a retrieval-ului, inclusiv filtrele de policy si de scope;
- m4-3 trebuie sa valideze augmentarea semantica fara sa inverseze ordinea de incredere sau sa piarda provenance.

Context pentru sprinturi:

- sprint-6 trebuie tratat ca sprint de contracte si mecanism deterministic, nu ca sprint de tuning semantic;
- sprint-7 trebuie sa inchida chunking, embeddings si rationale capture doar dupa ce ordinea retrieval-ului este deja blocata;
- sprint-8 trebuie sa lase retrieval-ul pregatit pentru consum de catre control plane si pilot, nu doar ca experiment izolat.

Context pentru taskuri si handoff catre agenti:

- pt-013 cere catalog de taskuri suportate si schema de evidence pack suficient de precisa incat un agent sa stie ce trebuie sa primeasca si ce nu are voie sa considere adevar;
- pt-014 cere implementarea traseului deterministic-first cu filtre structurale si de policy inainte de orice strat semantic;
- pt-015 cere semantic augmentation auditabila: chunks legate de versiuni canonice, vectori versiune-ati si rationale de selectie pentru fiecare element major inclus.

### Program Context for Epic 5: Agent Control Plane, Policy and Approvals

Ancore reale de context si evidenta:

- regulile de operare pentru agenti sunt deja codificate in plan: fara scrieri directe, fara presupuneri, fara ocolirea action broker-ului si cu audit complet pentru orice run material;
- `effective_delivery_track` are deja obiecte concrete pentru `prompt_template_registry`, `agent_run`, `agent_evidence` si `action_request`, ceea ce ofera o translatare operationala a control plane-ului;
- modelul de aprobare cerut este deja fixat ca `approval-record-plus-scope-plus-expiry-plus-post-execution-verification`.

Riscuri critice de continut inca deschise:

- authority chain-ul este inca modelat pe roluri, nu pe identitati reale sau grupuri concrete de aprobare;
- deny paths sunt definite conceptual, dar nu sunt inca enumerate pe fiecare clasa de tool si pe fiecare suprafata de write relevanta;
- prompt governance este bine pozitionata conceptual, dar fara un registry real exista risc ca implementarea sa alunece inapoi spre prompturi ad-hoc.

Context pentru milestone-uri:

- m5-1 trebuie sa defineasca politica executabila pe clase de risc si sa inchida ce este permis, ce este blocat si ce necesita aprobare;
- m5-2 trebuie sa operationalizeze ledger-ul de actiuni si aprobari astfel incat nicio scriere guvernata sa nu ocoleasca fluxul mediat;
- m5-3 trebuie sa inchida auditul complet al run-urilor agentice si guvernanta template-urilor de prompt.

Context pentru sprinturi:

- sprint-7 defineste fundatia de policy si deny-by-default;
- sprint-8 operationalizeaza aprobarea si executia mediata;
- sprint-9 trebuie sa dovedeasca faptul ca auditul si prompt governance sunt suficient de solide pentru pilot si readiness review.

Context pentru taskuri si handoff catre agenti:

- pt-016 cere clasificare de risc si policy matrix pe clase reale de actiuni, nu doar pe categorii generice;
- pt-017 cere workflow mediat cu scope, intent, expiry si outcome astfel incat fiecare write sa poata fi explicat si revocat conceptual;
- pt-018 cere registry de prompturi si ledger de run-uri care sa pastreze suficienta trasabilitate pentru review posterior si pentru investigatie de policy breach.

### Program Context for Epic 6: Delivery Control and Pilot Application Flow

Ancore reale de context si evidenta:

- planul fixeaza deja setul de artefacte obligatorii pentru pilot: research dossier, application definition pack, verification specification si evidence map;
- fluxul pilot trebuie sa consume context broker, retrieval broker, action broker si lantul de aprobare deja definite in program si in track-ul efectiv;
- infrastructura reala deja auditata si shared services-urile observate in cluster ofera materialul factual pentru selectia unui pilot bounded, dar nu justifica inca selectarea implicita a unei aplicatii anume fara aprobare explicita.

Riscuri critice de continut inca deschise:

- pilotul concret nu este inca selectat si aprobat, ceea ce ramane cel mai mare gap de continut din tot planul program-level;
- shared-service contracts necesare pentru pilot nu sunt inca transformate in pachet canonico-operational complet;
- fara doua rulari efective pe acelasi pilot, orice afirmatie de repeatability ramane inca nevalidata.

Context pentru milestone-uri:

- m6-1 trebuie sa inchida alegerea pilotului si setul complet de artefacte obligatorii, altfel restul epic-ului ramane o schema de validare fara obiect real;
- m6-2 trebuie sa produca prima dovada end-to-end ca platforma poate livra guvernat un rezultat real;
- m6-3 trebuie sa masoare sincer repeatability si sa converteasca orice bypass manual ramas in gap explicit al platformei.

Context pentru sprinturi:

- sprint-8 trebuie sa fixeze pilotul si artefactele sale, nu sa porneasca executia in orb;
- sprint-9 este sprintul de prima rulare guvernata si trebuie sa lase audit complet, nu doar rezultat functional;
- sprint-10 este sprintul de verificare a repetabilitatii si de transformare a gap-urilor in backlog legitim.

Context pentru taskuri si handoff catre agenti:

- pt-019 cere selectie bounded de pilot pe baza nevoii reale si a dependintelor deja observate, nu pe criterii de prestigiu sau complexitate maxima;
- pt-020 cere executia pilotului exclusiv prin fluxurile guvernate, cu brokeri, aprobari si verificare post-run;
- pt-021 cere a doua rulare si raportarea sincera a diferentelor, inclusiv acolo unde platforma inca depinde de interventie manuala.

### Program Context for Epic 7: Observability, Audit, Retention and Rollout

Ancore reale de context si evidenta:

- in infrastructura reala exista deja suprafete de observabilitate si operare partajate in jurul `orchestrator`, inclusiv Traefik si servicii din zona Prometheus, Grafana si Loki observate anterior in cluster;
- planul si track-ul efectiv cer explicit dashboards, alerting, retention, runbooks si KPI baseline pentru registry, discovery, retrieval si control plane;
- readiness review este deja definit ca mecanism de decizie bazat pe evidenta, nu pe optimism.

Riscuri critice de continut inca deschise:

- KPI-urile si SLO-urile nu au inca praguri numerice aprobate;
- retention-ul este cerut corect, dar nu are inca perioade concrete, clase de acces si cost boundaries fixate;
- runbooks nu exista inca drept artefacte reale, iar fara ele alerting-ul risca sa fie doar semnalizare fara raspuns disciplinat.

Context pentru milestone-uri:

- m7-1 trebuie sa transforme observabilitatea din intentie in suprafata operationala utilizabila de operatori;
- m7-2 trebuie sa inchida retention-ul, audit review si runbook-urile critice pentru scenariile relevante din wave-1;
- m7-3 trebuie sa produca review-ul de readiness cu gap register si decizie explicita de go sau hold.
- m7-4 trebuie sa inghete contractele de semnal si ownership-ul pentru toate suprafetele critice ale wave-1;
- m7-5 trebuie sa faca operative dashboard-urile shared, routing-ul alertelor si vederile KPI/SLO folosite in decizii reale;
- m7-6 trebuie sa demonstreze ca retention-ul, runbook linkage si drill-urile de observabilitate functioneaza in practica, nu doar pe hartie.

Context pentru sprinturi:

- sprint-9 porneste observabilitatea pe suprafetele deja construite si validate in epicele anterioare;
- sprint-10 inchide partea de retention si operare umana prin runbooks si procese de audit review;
- sprint-11 trebuie sa fie sprint de verdict, nu sprint de cosmetizare a problemelor ramase.
- sprint-20 trebuie sa fixeze contractele de semnal si adaptarea disciplinata la shared observability pe `orchestrator`;
- sprint-21 trebuie sa livreze dashboard pack-ul operational, alert routing-ul testat si vederile de decizie KPI/SLO;
- sprint-22 trebuie sa valideze linkage-ul catre runbooks, enforcement-ul retention si drill-ul de observabilitate pentru failure modes relevante.

Context pentru taskuri si handoff catre agenti:

- pt-022 cere KPI-uri si dashboards utile decizional pentru registry, discovery, retrieval, approvals si agent control, nu doar grafice decorative;
- pt-023 cere reguli reale de retention, acces la audit si runbooks pentru scenarii critice de degradare si incident;
- pt-024 cere review final onest, cu residual risks si open gaps, astfel incat extinderea wave-2 sa fie bazata pe evidenta acumulata in wave-1.
- pt-046 cere inventar explicit de semnale si owneri, astfel incat fiecare suprafata critica sa aiba semnificatie operationala clara;
- pt-047 cere contracte de expunere pentru metrics, logs si health queries astfel incat shared Prometheus, Loki si Grafana sa poata consuma date comparabile si utile;
- pt-048 cere interogari canonice de health si degradare care pot fi revizuite si versionate, nu doar explorari ad-hoc;
- pt-049 cere dashboard pack shared care sa faca vizibile starea registry-ului, ingestiei, retrieval-ului, approval backlog-ului si run-urilor de agenti;
- pt-050 cere contact points, routing si escaladare testate efectiv pentru alertele critice ale wave-1;
- pt-051 cere vederi KPI/SLO si error budget care pot fi folosite in readiness review si in decizii de hold sau proceed;
- pt-052 cere validarea enforcement-ului de retention pe suprafete reale, inclusiv evidenta si urmele de audit;
- pt-053 cere indexarea si legarea runbook-urilor din alerte si dashboard-uri pentru a evita semnalizarea fara raspuns operational;
- pt-054 cere drill de observabilitate pe scenarii relevante, pentru a demonstra ca suprafata operationala shared poate ghida raspunsul uman si analiza disciplinata.

### Program Context for Epic 8: Business Continuity, Backup, Restore and Disaster Recovery

Ancore reale de context si evidenta:

- runtime-ul `internalCMDB` este planificat pe `orchestrator`, cu date, backup-uri si exporturi pe `/mnt/HC_Volume_105014654/postgresql/internalcmdb/...`;
- planul curent cere deja retention, runbooks si readiness review, dar nu demonstreaza inca recoverability testata;
- accesul si topologia curenta indica o prima instanta operationala clara, ceea ce face decizia HA-versus-single-instance o chestiune de policy explicita, nu una care poate ramane implicita.

Riscuri critice de continut inca deschise:

- nu exista inca RTO/RPO aprobate formal;
- nu exista inca dovada de restore testat pentru `internalCMDB` si artefactele sale critice;
- nu exista inca verdict explicit daca single-instance este acceptat ca postura temporara sau daca se cere evolutie spre HA.

Context pentru milestone-uri:

- m8-1 inchide asteptarile de continuitate si elimina interpretarea libera a termenului `backup`;
- m8-2 valideaza ca restaurarea functioneaza, nu doar ca fisierele pot fi copiate;
- m8-3 transforma recovery intr-o disciplina testata si intr-un backlog de remediere, nu intr-un text aspirational.

Context pentru sprinturi:

- sprint-12 trebuie sa stabileasca obiectivele si postura de continuitate inainte de orice exercitiu de recuperare;
- sprint-13 trebuie sa combine restore testing cu scenarii de disaster suficient de realiste pentru infrastructura curenta.

Context pentru taskuri si handoff catre agenti:

- pt-025 cere definirea explicita a asteptarilor de continuitate si a posturii de disponibilitate;
- pt-026 cere backup si restore validate pe date si artefacte critice, nu pe exemple abstracte;
- pt-027 cere un exercitiu formal cu findings si actiuni, nu o simpla verificare de checklist.

### Program Context for Epic 9: Secrets, PKI and Trust Management

Ancore reale de context si evidenta:

- auditul de trust din 2026-03-08 pe `orchestrator`, `postgres-main` si nodurile `hz.*` a observat pe toate hosturile SSH-reachable verificate setari `permitrootlogin yes`, `pubkeyauthentication yes` si `passwordauthentication yes`, ceea ce confirma o postura SSH functionala dar inca permisiva care trebuie tratata ca risc explicit, nu ca presupunere tacita;
- acelasi audit a observat materiale de incredere si secrete distribuite pe hosturi diferite, inclusiv `root.crt` si chei SSH pe `postgres-main`, chei si artefacte `.env` pe `orchestrator` si `hz.164`, precum si certificate Let's Encrypt active pe `hz.164` pentru `geniuserp.app`, `manager.neanelu.ro` si `staging.cerniq.app`;
- pentru suprafetele PostgreSQL publice relevante pentru wave-1, probele TLS catre `postgres.neanelu.ro:5432` si `postgres.orchestrator.neanelu.ro:5432` au returnat `connection refused` la momentul auditului, deci planul trebuie sa trateze conectivitatea externa pe `5432` ca obiectiv de validare si nu ca stare deja demonstrata;
- control plane-ul si deny-by-default implica in mod natural un model mai strict pentru credențiale, secrete si materiale de incredere;
- infrastructura curenta include servicii shared si expuneri externe unde trust model-ul nu poate ramane implicit.

Riscuri critice de continut inca deschise:

- exceptia bootstrap poate deveni risc persistent daca nu este inchisa disciplinat;
- certificate lifecycle si trust anchors nu sunt inca detaliate operational;
- secret storage si privileged access review nu sunt inca transformate in fluxuri aprobate si auditate end-to-end.

Context pentru milestone-uri:

- m9-1 defineste unde traiesc secretele si cine le poate atinge;
- m9-2 inchide exceptiile bootstrap si impune separare reala pe roluri;
- m9-3 operationalizeaza lifecycle-ul pentru certificate si recuperarea din expirare sau compromitere.

Context pentru sprinturi:

- sprint-13 fixeaza boundaries si modelul de stocare;
- sprint-14 combina rotatia credentialelor cu lifecycle-ul de certificate pentru a reduce trust-ul implicit ramas din bootstrap.

Context pentru taskuri si handoff catre agenti:

- pt-028 cere boundary model pentru secrete si materiale PKI care sa poata fi revizuit formal;
- pt-029 cere reducerea concreta a expunerii bootstrap si auditarea accesului privilegiat;
- pt-030 cere lifecycle complet pentru certificate si cale de recovery pentru esecuri de incredere.

### Program Context for Epic 10: Supply Chain Security and Release Integrity

Ancore reale de context si evidenta:

- repo-ul contine componente Python, imagini containerizate si dependinte third-party care intra in runtime-ul platformei si in subproiectele suport;
- planul existent cere deja runtime packaging clar, release evidence si gates pe clase de risc, dar nu inchide inca provenienta software;
- folosirea de imagini Docker, pachete Python si toolchain-uri multiple cere control explicit de integritate pentru a sustine auditabilitatea enterprise.

Riscuri critice de continut inca deschise:

- lipsesc inventar complet, SBOM si scanari reviewabile pentru artefactele principale;
- nu exista inca policy aprobat pentru provenance si attestation;
- licentierea si acceptarea dependintelor third-party nu sunt inca transformate intr-o decizie de governance repetabila.

Context pentru milestone-uri:

- m10-1 stabileste ce trebuie controlat si din ce este compusa suprafata software reala;
- m10-2 activeaza scanarea si controlul de integritate ca poarta reala, nu doar raportare;
- m10-3 inchide provenance, attestation si baseline-ul de license review pentru artefactele promovate.

Context pentru sprinturi:

- sprint-14 produce inventarul si SBOM-ul;
- sprint-15 introduce gates operationale si contractul de provenienta pentru release-uri.

Context pentru taskuri si handoff catre agenti:

- pt-031 cere inventar si SBOM bazate pe componente reale din repo si runtime-uri aprobate;
- pt-032 cere scanare cu consecinte reale in gates de promovare;
- pt-033 cere policy de provenance si attestation suficient de precis incat un artefact promovat sa poata fi aparat la audit.

### Program Context for Epic 11: Environment Promotion and Release Management

Ancore reale de context si evidenta:

- planul spune deja onest ca nu urmareste o transformare CI/CD completa beyond platform needs, dar asta nu elimina nevoia de release governance;
- schimbarile pentru schema, runtime si brokeri cer oricum gates, rollback si dovezi de verificare dupa release;
- relatia cu `orchestrator` si cu activele runtime reale inseamna ca release-urile nu pot fi tratate ca exercitii pur locale.

Riscuri critice de continut inca deschise:

- promotion model-ul pe medii sau clase de mediu nu este inca fixat formal;
- migration rollback si release failure recovery nu sunt inca demonstrate ca discipline recurente;
- release evidence chain nu este inca completata cap-coada pentru artefactele platformei.

Context pentru milestone-uri:

- m11-1 defineste cum se misca schimbarile si cine aproba fiecare clasa de promovare;
- m11-2 inchide contractul de rollback si recovery pentru schimbarile cu impact operational real;
- m11-3 transforma release-ul intr-o secventa auditabila de la artifact la verificare post-release.

Context pentru sprinturi:

- sprint-15 trebuie sa fixeze environment classes si gates de promovare;
- sprint-16 trebuie sa valideze recovery si sa lege release evidence chain de integrity controls deja introduse.

Context pentru taskuri si handoff catre agenti:

- pt-034 cere promotion gates si approval matrix fara presupuneri despre un pipeline standard generic;
- pt-035 cere rollback drills si migration recovery explicite pentru suprafetele cu baza de date;
- pt-036 cere lant complet de evidenta pentru release, de la integritate la verificarea de dupa deploy.

### Program Context for Epic 12: LLM Runtime, Model Registry and Evaluation Governance

Ancore reale de context si evidenta:

- planul foloseste deja `embeddings_strategy: local-self-hosted` si retrieval bounded pentru agenti, ceea ce implica existenta unui strat de runtime si selectie de modele chiar daca nu era inca formalizat separat;
- repo-ul contine subproiecte si active din zona AI infrastructure care pot fi refolosite ca baza de conventii de deployment si observare;
- control plane-ul deja definit pentru agenti face imposibila tratarea modelelor ca detaliu nereglementat daca programul merge spre operare enterprise extinsa.

Riscuri critice de continut inca deschise:

- selectionarea modelelor si routing-ul lor nu sunt inca guvernate prin registry si policy aprobate;
- nu exista inca evaluation harness formal pe task types suportate;
- fallback, cost and latency guardrails si safety checks sunt inca doar necesitate recunoscuta, nu capacitate operationala demonstrata.

Context pentru milestone-uri:

- m12-1 fixeaza runtime-ul si registry-ul de modele ca suprafata guvernata;
- m12-2 inchide partea de evaluare comparativa repetabila;
- m12-3 inchide fallback, cost, latenta si safety ca reguli operationale, nu ca preferinte de laborator.

Context pentru sprinturi:

- sprint-16 defineste stack-ul si contractele de registry/routing;
- sprint-17 aduce benchmark-uri, evaluare si guardrails pana la nivelul de comportament controlat sub degradare.

Context pentru taskuri si handoff catre agenti:

- pt-037 cere model serving stack si routing rules legate de task types reale, nu doar listare de modele disponibile;
- pt-038 cere benchmark intern si evaluation harness care sa poata fi rerulat si auditat;
- pt-039 cere guardrails pentru fallback, cost si safety astfel incat degradarea modelului sa nu destabilizeze comportamentul platformei.

### Program Context for Epic 13: Capacity, Performance and Resilience Engineering

Ancore reale de context si evidenta:

- planul actual introduce deja PostgreSQL, pgvector, retrieval brokers si control plane, toate cu impact direct de latenta, throughput si crestere a datelor;
- infrastructura curenta si suprafetele partajate observate in cluster ofera punctul de plecare pentru modele de capacitate si semnale de performanta realiste;
- readiness review si observabilitatea deja cerute nu pot fi sustinute enterprise-grade fara praguri si exercitii de performanta si rezilienta.

Riscuri critice de continut inca deschise:

- nu exista inca model formal de crestere pentru date, embeddings si query volume;
- nu exista inca load characterization pentru registry si brokeri;
- fail-open versus fail-closed nu este inca inchis prin exercitii si policy pentru componentele critice.

Context pentru milestone-uri:

- m13-1 inchide modelul de capacitate si cost ca baza de planificare;
- m13-2 produce caracterizarea de performanta si concurenta pentru suprafetele critice;
- m13-3 transforma rezilienta si failure behavior intr-o capacitate reviewabila, nu intr-o speranta.

Context pentru sprinturi:

- sprint-17 produce baseline-ul de capacitate si cost;
- sprint-18 masoara performanta si exercita failure behavior pe componentele cheie.

Context pentru taskuri si handoff catre agenti:

- pt-040 cere model de crestere si cost bazat pe suprafetele reale ale platformei, nu pe sizing generic;
- pt-041 cere load/stress tests cu rezultate utile pentru praguri operationale si nu doar pentru benchmarking izolat;
- pt-042 cere exercitii de failure behavior si traducerea lor in reguli operationale si backlog de remediere.

### Program Context for Epic 14: Support Model, RACI Finalization and Service Operations

Ancore reale de context si evidenta:

- planul a definit de la inceput roluri de program, dar a spus explicit ca ele trebuie numite inainte de executia reala;
- observabilitatea, runbooks, approvals si review loops deja introduse cer un model uman de operare si suport ca sa functioneze in practica;
- extinderea dincolo de wave-1 nu poate fi sustinuta credibil fara ownership real si cadence-uri recurente de governance.

Riscuri critice de continut inca deschise:

- RACI-ul este inca implicit legat de roluri abstracte, nu de persoane sau grupuri concrete;
- suportul L1/L2/L3 si on-call nu sunt inca definite pentru suprafetele critice;
- recurring review cadences nu sunt inca activate ca mecanism de prevenire a drift-ului organizational.

Context pentru milestone-uri:

- m14-1 inchide ownership-ul nominal si service boundaries;
- m14-2 operationalizeaza modelul de suport, on-call si escaladare;
- m14-3 transforma governance-ul uman intr-o rutina recurenta, nu intr-o activitate one-off.

Context pentru sprinturi:

- sprint-18 finalizeaza ownership-ul si boundaries;
- sprint-19 operationalizeaza suportul si ritualurile recurente de review.

Context pentru taskuri si handoff catre agenti:

- pt-043 cere mapare pe owneri reali, nu doar confirmarea rolurilor abstracte deja existente in plan;
- pt-044 cere model executabil de suport si incident command pentru suprafetele critice;
- pt-045 cere calendar si input-uri obligatorii pentru review-uri recurente, astfel incat governance-ul sa nu se erodeze dupa lansare.

## Content: Approval-Ready Control Baselines for Wave-1

Aceasta sectiune inchide explicit gap-urile de continut ramase pentru wave-1 prin definirea unor baseline-uri aprobabile. Aceste baseline-uri nu trebuie tratate ca adevar deja aprobat daca nu exista semnatura formala a ownerilor relevanti, dar trebuie tratate ca propunerea implicita de lucru a planului pana la aprobarea sau ajustarea lor explicita.

Regula de utilizare:

- daca un owner aproba explicit aceste baseline-uri, ele devin normative pentru implementare;
- daca un owner le modifica, diferenta trebuie inregistrata ca delta de plan si propagata in handoff-urile afectate;
- daca lipseste ownerul sau aprobarea, baseline-ul ramane `approval-candidate` si nu poate fi prezentat drept stare aprobata finala.

### Wave-1 Supported Task Type Catalog

Task types suportate pentru wave-1 trebuie limitate la urmatoarele clase, pentru ca acestea sunt sustinute de blueprint, de activele reale din repo si de modelul operational deja decis pentru instanta curenta.

1. `infrastructure-readonly-analysis`
   Scop: analiza bounded a hosturilor, clusterelor, serviciilor shared si dependintelor lor folosind documente canonice, registry si date observate aprobate.
   Mandatory evidence: documente canonice relevante, query-uri registry pe entitatile din scope, observatii runtime cu provenance.
   Disallowed evidence: rezultate semantice globale fara filtrare structurata, capturi neprovenite din surse aprobate, memorii informale nevalidate.
   Write class: `read-only`.

2. `registry-query-and-evidence-lookup`
   Scop: compunerea de raspunsuri bounded pentru lookup operational, ownership, dependinte, provenienta si stare observata.
   Mandatory evidence: entity bindings, query contracts aprobate, evidence pack pentru entitatile in scope.
   Disallowed evidence: completari bazate pe similaritate semantica in absenta legaturilor canonice sau registry.
   Write class: `read-only`.

3. `canonical-document-authoring`
   Scop: creare sau actualizare bounded de documente canonice in Git, conform taxonomy si metadata schema aprobate.
   Mandatory evidence: template pack aprobat, bindings la entitati registry, owner si approval state definite.
   Disallowed evidence: redactare libera fara frontmatter valid, documente fara owner sau fara identificatori stabili.
   Write class: `bounded-repo-write`.

4. `registry-schema-and-migration-change`
   Scop: schimbari bounded la schema `internalCMDB`, migrari, seed taxonomies si dictionar de date.
   Mandatory evidence: ADR-uri relevante, impact analysis pentru retrieval/ingestion/audit, approval explicit pentru write.
   Disallowed evidence: modificari directe in baza fara lant de migrari si fara evaluare de impact.
   Write class: `controlled-schema-write`.

5. `discovery-collection-and-loader-run`
   Scop: rulare de colectori si loadere aprobate pentru actualizarea starii observate si a provenientei.
   Mandatory evidence: sursa de colectare aprobata, target scope explicit, provenance capture activ, contract de normalizare valid.
   Disallowed evidence: scripturi modificate ad-hoc fara review, SQL manual pentru repararea batch-urilor, write bypass in afara loaderelor guvernate.
   Write class: `controlled-data-write`.

6. `bounded-configuration-change`
   Scop: schimbari bounded de configuratie in repo sau runtime pentru suprafete deja modelate si aprobate.
   Mandatory evidence: configuration scope explicit, dependinte afectate, approval record valid, verificare post-change.
   Disallowed evidence: runtime mutation directa fara action broker, scope implicit, sau modificari care ating mai multe domenii fara extindere aprobata de scope.
   Write class: `bounded-runtime-or-repo-write`.

7. `governed-pilot-delivery-run`
   Scop: executia pilotului bounded prin brokeri, approvals si verificare post-run.
   Mandatory evidence: research dossier, application definition pack, verification specification, evidence map, approval chain activa.
   Disallowed evidence: bypass manual neauditat, lipsa oricarui artefact pilot mandatory, schimbari runtime in afara action broker-ului.
   Write class: `broker-mediated-governed-write`.

8. `observability-and-runbook-maintenance`
   Scop: definire sau actualizare bounded de dashboards, alerting, retention rules si runbooks pentru suprafetele wave-1.
   Mandatory evidence: KPI/SLO catalog relevant, surse de semnal aprobate, scenarii operationale reale, review de owner.
   Disallowed evidence: alerte fara runbook, retention fara justificare de audit sau cost, dashboard-uri decorative fara decizie operationala asociata.
   Write class: `bounded-ops-write`.

Task types explicit nesuportate in wave-1:

- `unbounded-autonomous-remediation`;
- `cross-domain-bulk-refactoring-without-approved-scope`;
- `high-risk-infrastructure-change-without-human-approval`;
- `production-data-rewrite-without-reconciliation-or-backout-model`;
- `global-semantic-discovery-without-structured-prefiltering`.

### Deny Paths and Default Blocking Rules

Deny paths obligatorii pentru wave-1:

- se refuza orice write daca lipseste `approval_record` valid pentru clasa de risc respectiva;
- se refuza orice actiune a carei intentie nu este legata explicit de scope-ul cerut si de artefactele de intrare aprobate;
- se refuza orice write path care nu trece prin action broker, inclusiv SQL direct, editare runtime directa sau hotfix operational neauditabil;
- se refuza orice retrieval care incearca semantic search global fara exact lookup si metadata filtering acolo unde exista date structurate;
- se refuza orice task care amesteca fapte canonice cu observatii neverificate fara marcarea conflictului si fara escaladare;
- se refuza orice task de pilot daca lipseste unul dintre artefactele obligatorii sau daca dependintele shared service nu sunt documentate;
- se refuza orice schimbare de schema sau taxonomie daca impactul asupra ingestiei, retrieval-ului, auditului si query contracts nu este inclus in handoff;
- se refuza orice actualizare a planului in afara campurilor YAML `status` pentru obiectele de executie;
- se refuza orice run material care nu poate produce `run_code`, `requested_scope`, `evidence_pack` sau echivalentul lor auditabil;
- se refuza orice promovare la `completed` fara verificare critica finala si fara dovada inchiderii gap-urilor de implementare cunoscute.

Exceptions handling rule:

- nu exista exceptii implicite;
- orice exceptie aprobata trebuie sa contina motiv, owner, expirare, masura compensatorie si plan de revenire la regula standard.

### Approval-Candidate KPI and SLO Threshold Baseline

Pragurile de mai jos sunt baseline-uri aprobabile pentru wave-1. Ele sunt alese pentru o instanta initiala bounded, single-reference-cluster, si trebuie confirmate sau ajustate dupa primele rulari reale instrumentate.

1. `discovery_freshness_core_hosts`
   Definition: vechimea maxima a ultimei observatii de succes pentru hosturile si nodurile de infrastructura in scope.
   Approval-candidate SLO target: `<= 24h`.
   Warning threshold: `> 24h and <= 48h`.
   Breach threshold: `> 48h`.

2. `discovery_freshness_shared_services`
   Definition: vechimea maxima a ultimei observatii de succes pentru serviciile shared critice din wave-1.
   Approval-candidate SLO target: `<= 24h`.
   Warning threshold: `> 24h and <= 72h`.
   Breach threshold: `> 72h`.

3. `registry_binding_coverage`
   Definition: procentul entitatilor wave-1 active care au binding la cel putin un artefact canonic relevant.
   Approval-candidate SLO target: `>= 95%`.
   Warning threshold: `< 95% and >= 90%`.
   Breach threshold: `< 90%`.

4. `reconciliation_unresolved_high_severity_age`
   Definition: varsta maxima admisa pentru discrepante high-severity intre canonical si observed state fara owner si actiune.
   Approval-candidate SLO target: `<= 2 business days`.
   Warning threshold: `> 2 and <= 5 business days`.
   Breach threshold: `> 5 business days`.

5. `evidence_pack_completeness_supported_tasks`
   Definition: procentul rularilor pentru task types suportate in care toate dovezile mandatory sunt prezente in evidence pack.
   Approval-candidate SLO target: `>= 99%`.
   Warning threshold: `< 99% and >= 97%`.
   Breach threshold: `< 97%`.

6. `approval_turnaround_standard_bounded_write`
   Definition: timpul dintre crearea cererii de actiune si decizia de aprobare pentru bounded writes standard.
   Approval-candidate SLO target: `<= 1 business day`.
   Warning threshold: `> 1 and <= 2 business days`.
   Breach threshold: `> 2 business days`.

7. `unauthorized_write_denial_rate`
   Definition: procentul tentativelor de write neaprobate care sunt blocate corect de control plane.
   Approval-candidate SLO target: `100%`.
   Warning threshold: `anything below 100% is a breach`.
   Breach threshold: `< 100%`.

8. `pilot_repeatability_success_rate`
   Definition: raportul dintre pasii obligatorii ai pilotului care ruleaza identic sau explicabil intre prima si a doua executie guvernata.
   Approval-candidate SLO target: `100% of mandatory steps repeatable or explicitly explained by approved delta`.
   Warning threshold: `any unexplained variance in non-critical steps`.
   Breach threshold: `any unexplained variance in critical or approval-gated steps`.

9. `alert_actionability_rate`
   Definition: procentul alertelor active care au runbook si owner asociat.
   Approval-candidate SLO target: `100%`.
   Warning threshold: `< 100% and >= 95%`.
   Breach threshold: `< 95%`.

10. `audit_record_completeness`
    Definition: procentul run-urilor materiale pentru care exista scope, evidence, decision trail, approvals si verification outcome.
    Approval-candidate SLO target: `100%`.
    Warning threshold: `anything below 100% is a breach candidate`.
    Breach threshold: `< 100%`.

Threshold governance rule:

- daca primele doua cicluri masurate reale arata ca un prag este prea lax sau prea strict, el trebuie recalibrat prin review formal, nu ajustat tacit in implementare;
- pentru orice prag numeric ramas neaprobat la momentul handoff-ului, agentul trebuie sa-l trateze ca `approval-candidate` si sa ceara confirmare de owner inainte de a raporta conformitate finala.

### Retention and Access Classes for Audit and Evidence Artifacts

Clasele de retention pentru wave-1 trebuie sa fie urmatoarele.

1. `collection-output-short-lived`
   Artifact classes: output brut de colectare, fisiere temporare de export, capturi intermediare necanonice.
   Approval-candidate retention: `30 days`.
   Default access: discovery owner, platform engineering lead, audit reviewers on demand.
   Rationale: utile pentru debugging si replay scurt, dar nu trebuie pastrate indefinit daca sunt substituite de fapte normalizate si evidence artifacts persistente.

2. `reconciliation-and-quality-reports`
   Artifact classes: rapoarte de reconciliere, coverage reports, freshness reports, quality anomaly reports.
   Approval-candidate retention: `180 days`.
   Default access: platform program manager, data registry owner, discovery owner, audit reviewers.
   Rationale: necesare pentru urmarirea trendurilor si a gap-urilor pe parcursul wave-1.

3. `evidence-pack-and-agent-context`
   Artifact classes: evidence packs, evidence pack items, rationale de selectie, context summaries pentru run-uri materiale.
   Approval-candidate retention: `180 days` minimum.
   Default access: platform engineering lead, security and policy owner, designated audit reviewers, domain owner when run-ul vizeaza domeniul lui.
   Rationale: necesare pentru audit, dispute review si analiza calitatii retrieval-ului.

4. `agent-run-and-approval-ledger`
   Artifact classes: agent runs, approval records, action requests, deny decisions, post-execution verification records.
   Approval-candidate retention: `365 days` minimum.
   Default access: security and policy owner, executive sponsor, platform program manager, designated audit reviewers.
   Rationale: reprezinta coloana vertebrala a trasabilitatii pentru actiuni materiale si trebuie pastrate cel mai mult dintre artefactele operationale wave-1.

5. `canonical-pilot-artifacts`
   Artifact classes: research dossier, application definition pack, verification specification, evidence map si variantele lor aprobate.
   Approval-candidate retention: `retain for full life of wave-1 plus any active wave-2 onboarding period`.
   Default access: domain owners, platform architecture lead, platform program manager, audit reviewers.
   Rationale: sunt artefacte canonice, nu doar output operational, si trebuie pastrate cat timp valideaza modelul programului.

Retention enforcement rules:

- stergerea sau arhivarea unui artifact nu poate rupe posibilitatea de a audita o decizie materiala in intervalul de retention aprobat;
- daca un artifact face parte dintr-un incident, dispute review sau exception path deschis, retention-ul se suspenda pana la inchiderea formala a cazului;
- access-ul la clasele de retention trebuie acordat pe need-to-know si roluri aprobate, nu pe convenience operational.

### Pilot Selection Criteria for the First Governed Wave-1 Pilot

Criteriile de selectie pentru primul pilot trebuie sa fie cumulative, nu optionale.

1. Pilotul trebuie sa fie `bounded` pe un singur produs sau suprafata functionala clara.
2. Pilotul trebuie sa consume direct entitati si relatii reale deja modelabile in `internalCMDB`.
3. Pilotul trebuie sa poata demonstra retrieval bounded si provenance-backed, nu doar rendering de UI sau output narativ.
4. Pilotul trebuie sa aiba dependinte shared service identificabile si suficient de stabile pentru a fi documentate canonic.
5. Pilotul nu trebuie sa necesite din prima write-uri high-risk in infrastructura de productie.
6. Pilotul trebuie sa poata fi rulat de doua ori in conditii comparabile pentru validarea repeatability.
7. Pilotul trebuie sa produca valoare operationala reala pentru operatori sau owneri de platforma, nu doar un demo vizual.
8. Pilotul trebuie sa poata fi verificat prin acceptance checks bazate pe evidenta, nu pe evaluare subiectiva.
9. Pilotul trebuie sa reuseasca active reale deja existente in repo si in cluster, nu sa depinda de un nou ecosistem extern neauditat.
10. Pilotul trebuie sa fie suficient de mic incat orice gap ramas sa poata fi atribuit platformei, nu complexitatii excesive a cazului.

Tie-break rule pentru selectie:

- daca mai multe candidate satisfac criteriile de mai sus, se alege candidatul cu cea mai mare densitate de validare pentru registry plus retrieval plus audit, nu candidatul cu cea mai mare suprafata de business.

Wave-1 recommended pilot baseline:

- baseline-ul recomandat ramane aplicatia interna read-only de interogare si navigare a `internalCMDB` pentru operatori, deoarece valideaza direct registry-ul, retrieval-ul bounded, evidence traceability si disciplina de delivery fara a introduce prematur write automation cu risc mare.

Pilot disqualification criteria:

- necesita integrare noua externa majora care nu este deja auditata sau modelata;
- necesita write-uri production-high-risk inainte de validarea control plane-ului;
- nu poate produce dovezi clare de provenienta pentru raspunsurile cheie;
- nu poate fi rerulat comparabil intr-un al doilea ciclu guvernat;
- depinde de cunoastere tacita neredusa in artefacte canonice.

## Content: Critical Enterprise Completeness Gap Register Beyond Wave-1 Foundation

Aceasta sectiune face explicita distinctia dintre:

- plan material complet pentru fundatia enterprise wave-1;
- plan complet enterprise-wide in sens maximal, multi-workstream, cu operare matura si validari repetate.

Verdict normativ de interpretare:

- documentul de fata nu poate fi prezentat onest ca `100% complet` sau `100% corect` in sens enterprise absolut;
- documentul poate fi prezentat onest ca `materially complete for wave-1 foundation` si `expanded-enterprise-draft-for-implementation-review`;
- orice claim mai puternic necesita inchiderea formala a gap-urilor de mai jos prin artefacte, aprobari, teste si operare sustinuta.

Gap domains care raman in afara completitudinii absolute actuale:

1. Business continuity, backup, restore and disaster recovery.
   Gap concret: lipsesc RTO/RPO aprobate, restore drills periodice, scenarii de failover, exercitii de disaster simulation si decizia explicita de toleranta sau non-toleranta la single-instance failure pentru `internalCMDB`.

2. Secrets management, PKI and trust lifecycle.
   Gap concret: lipsesc secret storage standardizat, rotatie de credentiale, lifecycle pentru certificate, private key handling, trust model intern si review periodic pentru acces privilegiat.

3. Supply chain security and software integrity.
   Gap concret: lipsesc SBOM, dependency scanning formal, image scanning, signing/provenance pentru artefacte, verificare de licente si control explicit asupra surselor third-party.

4. Environment promotion and release governance.
   Gap concret: lipsesc modele complete de promotion gates, artifact governance, release approval per environment, rollback drills si lanturi de evidenta pentru release management.

5. Named RACI, support model and service operations.
   Gap concret: rolurile sunt definite la nivel de plan, dar nu exista inca persoane sau grupuri reale numite, nici L1/L2/L3 support model, on-call, incident command model sau cadence-uri de service review.

6. Capacity, cost, performance and resilience engineering.
   Gap concret: lipsesc capacity model pentru PostgreSQL si vector storage, load/concurrency targets pentru brokeri, cost envelope, stress tests, failure injection si latency budgets pe task type.

7. LLM runtime, model registry and evaluation governance.
   Gap concret: planul acopera control plane-ul agentilor, dar nu inchide operational model serving stack, model registry, fallback strategy, evaluation harness, red-team tests si governance pentru runtime-ul modelelor self-hosted.

8. Data governance and internal compliance controls.
   Gap concret: lipsesc data classification matrix, redaction rules, access review cadence, privileged access review, exception register de conformitate si tratament explicit pentru date sensibile sau personale.

9. Sustained operation proof versus milestone acceptance.
   Gap concret: unele milestone-uri inchid definirea sau activarea initiala, dar nu demonstreaza inca operare repetata, review recurent si comportament stabil in timp.

10. Full cross-environment drift governance.
    Gap concret: exista drift detection canonical-versus-observed, dar nu este inca completata disciplina pentru migration drift, broker/policy/runtime drift, taxonomy upgrade playbooks si backward compatibility rules pentru evidence packs si prompt templates.

### Supplemental Enterprise Workstreams Required for Absolute Enterprise Completeness

Planul livrabil actual inchide fundatia wave-1. Cele 9 workstream-uri de mai jos nu anuleaza aceasta fundatie, ci definesc cerinta pentru completitudine enterprise-wide maxima. Fiecare bloc are criterii testabile, artefacte obligatorii, cerinte de drill si cerinte de operare sustinuta. Absenta oricarui bloc nu invalideaza wave-1 foundation dar invalideaza orice pretentie de complete enterprise operating model.

**Regula de interpretare obligatorie:** un bloc este considerat inchis formal numai daca toate criteriile de acceptanta sunt indeplinite simultan, nu daca o parte din ele sunt bifate. TBD-ul explicit in locul unui owner real este un gap blocker, nu un placeholder acceptabil pentru inchidere.

---

#### Bloc 1 — Epic 8: Business Continuity, Backup, Restore and Disaster Recovery

Scop: definirea si validarea unei posturi explicite de continuitate pentru `internalCMDB` si artefactele sale critice, cu RTO/RPO aprobate si exercitii formale executate si inregistrate.

**Postura wave-1 acceptata explicit:**

- Single-instance deployment pe `orchestrator`; HA nu este ceruta pentru wave-1.
- Decizia de single-instance trebuie documentata intr-un document de tip `policy_pack` cu owner si data de semnatura.
- HA este obligatorie inainte de orice pretentie de wave-2 multi-domain scale-out.

**Thresholds aprobate obligatorii:**

- RTO ≤4h pentru `internalCMDB` in caz de failure total al serviciului (recuperare manuala acceptata pentru wave-1).
- RPO ≤24h pentru PostgreSQL state (nightly pg_dump minim obligatoriu pe volumul `HC_Volume_105014654`).
- RPO ≤7d pentru artefacte de audit non-critice.
- Orice deviere de la aceste thresholds necesita document de risk acceptance semnat de `executive_sponsor`.

**Artefacte obligatorii:**

- `rto-rpo-baseline`: document `policy_pack`, semnat de `executive_sponsor` si `sre_observability_owner`.
- `ha-posture-acceptance`: document `policy_pack` cu decizie binara (single-instance-accepted / HA-required) si rationale.
- `backup-procedure`: runbook testat cu path-uri exacte pe `orchestrator` si volumul de date.
- `restore-procedure`: runbook testat cu pasi de validare (query de verificare post-restore obligatoriu).
- `restore-evidence-record`: document `backup_restore_record` produs dupa fiecare drill.
- `dr-exercise-findings`: raport cu findings actionabile, nu doar confirmare binara de succes.
- `corrective-actions-register`: entry in `governance.change_log` pentru fiecare finding deschis.

**Drill requirements:**

- Primul drill de restore: obligatoriu inainte de inchiderea `m8-2`; trebuie sa restaureze starea intr-un schema sau db separata si sa valideze query-urile cheie.
- DR simulation (failure de host PostgreSQL): obligatorie inainte de inchiderea `m8-3`.
- Cadenta minima: anual dupa wave-1 GA; rezultatele inregistrate in `evidence_pack`.

**Owner gap rule:** daca slotul `sre_observability_owner` este TBD, `m8-1` nu poate fi marcat completed. TBD este blocker explicit, nu placeholder.

---

#### Bloc 2 — Epic 9: Secrets, PKI and Trust Management

Scop: eliminarea credentialelor ad-hoc, definirea unui model complet de secret storage cu tooling named, rotatie si lifecycle de certificate operationalizat.

**Decizie obligatorie de secret storage (ADR named, inainte de m9-1):**

- Tooling-ul trebuie ales si documentat intr-un ADR inainte de inchiderea `m9-1`.
- Optiuni acceptabile: Docker Secrets, age-encrypted files cu permisiuni 0600 minime, HashiCorp Vault, SOPS cu backend aprobat.
- Stocarea secretelor in `.env` files fara restrictie de permisiuni sau in git history este conditie de esec automat pentru `m9-1`.

**Clase de credentiale gestionate obligatoriu:**

- bootstrap: temporare; trebuie rotate sau dezafectate inainte ca `epic-5` (policy engine) sa intre in productie.
- service-to-service: `internalCMDB app → PostgreSQL`; trebuie sa foloseasca credential rotabila, nu hardcodata.
- admin: root SSH pe `orchestrator` si `postgres-main`, DB superuser; accesul trasat si periodic reviewed.
- external: certificate TLS pentru orice endpoint expus public; renewal process obligatoriu.

**Certificate lifecycle rules:**

- Certificatele care expira in mai putin de 30 de zile declanseaza procesul de reneware.
- Certificate wildcard fara owner explicit documentat in `change_log` sunt interzise.
- CA self-signed: trebuie sa existe un scope document si un expiry management plan.

**Artefacte obligatorii:**

- `secrets-storage-adr`: decizie tehnica documentata cu tool ales, scope si access model.
- `credential-class-register`: inventar al tuturor claselor de credentiale cu owner, rotation schedule si status curent.
- `bootstrap-secret-rotation-evidence`: dovada ca credentialele bootstrap au fost rotate sau decommissionate.
- `tls-lifecycle-plan`: document operational cu renewal triggers, responsabili si recovery procedure.
- `privileged-access-review-record-cycle-1`: primul review complet, obligatoriu inainte de `m9-3`.

**Drill/test requirement:** primul privileged access review obligatoriu inainte de `m9-3`; cadenta trimestriala dupa aceea.

**Owner gap rule:** daca `security_and_policy_owner` este TBD, `m9-1` este blocat explicit.

---

#### Bloc 3 — Epic 10: Supply Chain Security and Software Integrity

Scop: controlul integritatii artefactelor software cu tooling explicit, thresholds de acceptanta pentru vulnerabilitati si review de licente.

**Decizie de tooling SBOM (obligatorie inainte de m10-1):**

- SBOM generation: Syft (recomandat pentru Python + container inventory) sau echivalent documentat in ADR.
- Vulnerability scan: Trivy sau echivalent aprobat.
- Format obligatoriu: SPDX 2.3 sau CycloneDX 1.4+.
- Scope acoperit obligatoriu: Python packages din `internalCMDB`, imagini Docker din `docker-compose.yml` si `llm.yml`.

**Scanning thresholds obligatorii:**

- CRITICAL CVEs in imagini promovate: zero fara exception aprobata explicit in exception register.
- HIGH CVEs: reviewed in 5 zile lucratoare de la descoperire; patch sau exception documentata inainte de urmatorul sprint release.
- Scan results: stocate ca `evidence_pack` document legat de release record.

**License review:**

- Verificare compatibilitate licente pentru toate dependintele din scope (GPL contamination check).
- Completata inainte de `m10-3`.

**Artefacte obligatorii:**

- `sbom-baseline`: SBOM complet in format standardizat.
- `dependency-scan-results-v1`: rezultate de scan cu severitate, remediation notes si decizii de exceptie.
- `image-scan-results-v1`: imagini scanate cu findings si status.
- `integrity-policy`: policy document cu tooling ales, thresholds si exceptii acceptate.
- `license-review-baseline`: lista de dependente cu licenta, status de compatibilitate si flaguri.

**Owner gap rule:** daca `security_and_policy_owner` este TBD, `m10-1` nu poate fi inchis.

---

#### Bloc 4 — Epic 11: Environment Promotion and Release Governance

Scop: standardizarea promotiei intre medii cu gates explicite, dovezi de rollback si traseabilitate completa per release.

**Mediile explicite ale acestui program:**

- `local-dev`: masina macOS a dezvoltatorului; governance obligatorie: branch naming si teste locale.
- `integration`: serviciu pe `orchestrator` in stare non-production; schimbarile de schema trebuie testate si validate inainte de promotia la production.
- `production`: `orchestrator` (internalCMDB runtime activat); necesita aprobare formala si rollback contract documentat.

**Promotion gates obligatorii:**

- Schema migration: testata in `integration`, revizuita de cel putin 1 approver, data loss verificata explicit (zero tolerance).
- Application changes: code review complet, toate testele trec, scan results revizuite fara CRITICAL deschis.
- Rollback contract: documentat pentru fiecare migrare inainte de promotia la `production`.

**Rollback drill requirement:**

- Cel putin un rollback drill complet inainte de prima migrare de schema in `production`.
- Rezultatele stocate ca `evidence_pack` legat de `m11-2`.

**Artefacte obligatorii:**

- `environment-classification-doc`: tipuri de medii, scope si reguli de promotie.
- `promotion-gates-policy`: gates explicite per clasa de schimbare.
- `release-approval-matrix`: cine aproba ce clasa de release.
- `rollback-contracts-pack`: rollback contract per migrare in scope.
- `rollback-drill-evidence`: record de drill cu scenario si rezultat.
- `deployment-evidence-chain`: pentru fiecare release in `production`, traseul complet de la artifact integrity la aprobare si post-release verification.

---

#### Bloc 5 — Epic 14: Named RACI, Support Model and Service Operations

Scop: trecerea de la roluri abstracte la model operational uman complet cu owners reali, tiers de suport definite si cadente de review cu output obligatoriu.

**TBD-as-explicit-blocker rule (non-negociabila):**

- Orice rol abstract in RACI fara un owner real sau team real = blocker explicit pentru `m14-1`.
- TBD trebuie sa apara ca field `tbd_owner_gap: true` in ownership matrix, nu omis tacit.
- RACI cu roluri neatribuite nu poate fi marcat approved.

**Support tier model:**

- L1: alert response initial, health check, restart procedural; responsabil: `platform_engineering_lead` sau delegate nominalizat explicit.
- L2: diagnosticare root cause, executie runbook; responsabil: `platform_engineering_lead`.
- L3: problema la nivel de arhitectura, escaladare externa sau schimbare de design; responsabili: `architecture_board` + `executive_sponsor`.
- On-call window wave-1: business hours definite explicit; after-hours escalation path documentat.
- P1 SLA: ≤2h pentru a ajunge la L2; ≤4h pentru implicarea `executive_sponsor`.

**Cadente de review obligatorii cu output documentat:**

- Lunar: service health review (dashboard + alerts + open action items); minutes inregistrate.
- Trimestrial: privileged access review (who has what, any changes needed); output documentat in `change_log`.
- Post-incident: incident review in maximum 5 zile lucratoare; corrective actions in `change_log`.

**Artefacte obligatorii:**

- `named-raci-matrix`: ownership matrix cu names reale sau TBD explicit marcat ca gap.
- `service-boundary-map`: servicii critice, tiers asociate, boundaries de responsabilitate.
- `on-call-and-escalation-rules`: SLA-uri, contacte, proceduri.
- `l1-l2-l3-support-playbook`: playbook executabil per tier.
- `ownership-acceptance-records`: fiecare owner semneaza acceptul responsabilitatii.
- `service-review-minutes-cycle-1`: minutes de la primul service review lunar.

---

#### Bloc 6 — Epic 13: Capacity, Cost, Performance and Resilience Engineering

Scop: cuantificarea si validarea capacitatii, performantei si comportamentului la esec al platformei cu thresholds numerice explicite si failure injection exercitata.

**Capacity model wave-1 baseline (bazat pe infrastructura observata):**

- `host`: ~15 rows (11 hz.\* + orchestrator + postgres-main + imac).
- `service`: ~50–100 rows (estimate pe baza serviciilor observate in audit 2026-03-08).
- `observed_fact`: ~500–2,000 rows baseline; crestere ~200/luna cu colectari saptamanale.
- `chunk_embedding` (pgvector): ~1,000 rows corpus initial de documente.
- `collection_run`: ~52/an cu cadenta saptamanala.
- Total tinta wave-1 GA: ≤10,000 rows aggregate; wave-2 tinta: ≤100,000 rows.

**Latency budgets obligatorii:**

- Registry point lookup (host by PK): <50ms p95.
- Registry list query (services per host): <200ms p95.
- Retrieval evidence pack assembly (bounded task): <2s p95.
- Action broker approval path: <500ms p95.

**Load test scope obligatoriu:**

- Minim 50 concurrent registry lookups fara degradare observabila.
- Rezultate stocate ca `evidence_pack` inainte de `m13-2` closure.

**Failure injection scenarios obligatorii (minim):**

- PostgreSQL service restart pe `orchestrator` → internalCMDB trebuie sa detecteze si sa raporteze, nu sa corupа starea.
- Disk near-full pe `HC_Volume_105014654` → write-path behavior definit explicit (reject cu eroare clara, nu silent data loss).
- Broker crash → registry trebuie sa ramana stabil; broker restart trebuie sa fie graceful.
- `fail-open vs fail-closed` rules: documentate explicit per componenta inainte de `m13-3`.

**Cost envelope wave-1:**

- Complet self-hosted; zero costuri API externe fara decizie explicita.
- Daca LLM extern este activat: cost cap lunar definit inainte de activare, owner de cost nominalizat.
- pgvector in-PostgreSQL: zero cost suplimentar de infrastructura.

**Artefacte obligatorii:**

- `capacity-model-doc`: tabel cu row estimates, growth model, storage footprint.
- `latency-budget-baseline`: thresholds per surface cu metoda de masurare.
- `load-test-results-v1`: rezultate cu concurrency, p95, saturation indicators.
- `failure-injection-report-v1`: scenarios, findings, fail-open/fail-closed decisions.
- `cost-envelope-policy`: decizie de cost cu cap, owner si trigger de escaladare.

---

#### Bloc 7 — Epic 12: LLM Runtime, Model Registry and Evaluation Governance

Scop: operationalizarea completa a runtime-ului de modele self-hosted cu model registry guvernat, evaluation harness repetabil si safety controls testate formal.

**Model registry: campuri obligatorii per intrare:**

- `model_id`, `model_class` (completion / embedding / reranker), `version`.
- `evaluated_at`, `evaluation_harness_run_id` (FK la evidence_pack).
- `supported_task_types`: lista de task type ID-uri aprobate.
- `latency_budget_p95_seconds`: numeric, obligatoriu.
- `cost_class` (free / token-based / compute-billed).
- `safety_review_at`, `safety_findings` (text sau null daca zero findings).
- `fallback_model_id` (FK la un alt model inregistrat sau null).

**Evaluation harness requirements:**

- Trebuie sa acopere ≥3 task types suportate.
- Rezultatele stocate in `evidence_pack` legate de versiunea de model.
- Benchmark repeat-testabil: rulat de doua ori pe acelasi task set trebuie sa produca rezultate in tolerance.
- Model selection trebuie sa citeze rezultate de evaluare, nu preferinta operatorului.

**Red-team minimum scope (obligatoriu inainte de operational approval):**

- Prompt injection: incercare de a overrida system prompt prin vector content malitios.
- Data exfiltration: incercare de a extrage continut din registry prin manipulare de prompt.
- Role confusion: incercare de a face agentul sa claim actiuni in afara policy scope-ului sau.
- Toate findings documentate in `evidence_pack` de tip safety review inainte de `m12-3` closure.

**Fallback triggers expliciti:**

- Local model p95 latency >10s pentru orice task type suportat → trigger automat de fallback.
- Error rate >5% in fereastra de 5 minute → fallback trigger.
- Fallback target: model inregistrat cu propriul latency budget SAU defined degraded-mode response documentata.

**Artefacte obligatorii:**

- `model-registry-contract`: schema si campuri obligatorii per model inregistrat.
- `evaluation-harness-spec`: task set, metode, tolerance thresholds.
- `model-evaluation-results-v1`: rezultate pentru modelele curente in use.
- `safety-and-red-team-report-v1`: findings, status si decizia de aprobare.
- `fallback-strategy-doc`: trigger conditions, target models, degraded-mode behavior.
- `latency-and-cost-guardrails-policy`: thresholds si escaladare.

---

#### Bloc 8 (NOU) — Epic 15: Data Governance and Internal Compliance Controls

Scop: clasificarea datelor stocate in registry, aplicarea redactarii la ingestie, gestionarea retentiei si construirea unui registru de exceptii auditabil cu declaratie de conformitate aprobata.

**Data classification matrix (wave-1 internalCMDB):**

| Clasa | Exemple                                                       | Restrictie                                                                 |
| ----- | ------------------------------------------------------------- | -------------------------------------------------------------------------- |
| A     | Host FQDN, service names, port numbers, observed status flags | Interna, fara restrictii suplimentare                                      |
| B     | IP addresses, user accounts observate, SSH key fingerprints   | Acces limitat la roluri platform_engineering; exclusa din retrieval public |
| C     | Credentiale, private keys, bootstrap secrets                  | NU trebuie stocate in registry; numai in approved secret storage           |
| D     | Date personale (email, nume)                                  | Interzise in wave-1 fara aprobare explicita DPO-equivalent                 |

**Redaction/masking rules obligatorii la ingestie:**

- Scanner la ingest: orice `observed_fact` sau chunk care contine pattern de tip credential trebuie RESPINS, nu inregistrat.
- Patterns minime de detectat: `-----BEGIN.*PRIVATE KEY-----`, `password=`, `secret=`, `api_key=`, `token=` in context de valoare.
- Rejection trebuie logat in `collection_run` cu statusul `rejected_sensitive_content`.

**Access control rules:**

- Class B: role check obligatoriu la query time; exclusa din retrieval public.
- Class C in registry: daca este descoperita, se declanseaza procedura de incident (cleanup + postmortem).
- Access review: trimestrial, documentat in `change_log`.

**Retention and deletion:**

- `observed_fact` fara legatura la `evidence_pack` activ: retine 90 zile, apoi delete conform procedurii.
- `agent_run` si `evidence_pack`: retine 1 an pentru audit, apoi archive sau delete aprobat.
- `chunk_embedding`: retine pana la retragerea documentului parinte + 30 zile.
- Runbook de deletie: documentat si testat per clasa de date inainte de `m15-3`.

**Exception register:**

- Orice abatere de la regulile de clasificare inregistrata in `governance.change_log` cu aprobare explicita.
- Exceptii fara remediation plan dupa 30 zile → escaladare la `security_and_policy_owner`.

**Artefacte obligatorii:**

- `data-classification-matrix`: document `policy_pack` cu toate clasele, exemple si restrictii.
- `ingest-redaction-policy`: reguli de scanner si rejection procedure.
- `access-control-model-for-classified-data`: cine acceseaza ce si in ce conditii.
- `retention-and-deletion-runbook`: per clasa de date, cu pasi testati.
- `exception-register-baseline`: registru initial cu eventuale exceptii deja cunoscute.
- `data-governance-compliance-declaration`: document `operational_declaration` semnat de `executive_sponsor`.

**Owner gap rule:** `security_and_policy_owner` trebuie sa fie o persoana sau team real inainte de `m15-1` closure.

---

#### Bloc 9 (NOU) — Epic 16: Sustained Operation Proof

Scop: demonstrarea ca platforma nu a fost doar initial activata, ci este operata repetat, cu dovezi concrete din cel putin al doilea ciclu operational si fara regresie intre cicluri.

**Principiu fundamental:** o operatiune executata o singura data este o demonstratie de setup. Operarea executata de doua ori sau mai mult, cu rezultate comparabile si fara regresie nedocumentata, este operare sustinuta. Aceasta distinctie este non-negociabila pentru inchiderea Epic 16.

**Proof requirements (toate obligatorii):**

1. Backup/restore drill: executat de cel putin doua ori; al doilea drill executat de un operator diferit de primul (daca este posibil); ambele rezultate stocate in `evidence_pack`.
2. Load test: rulat de doua ori cu rezultate comparate; orice degradare documentata ca finding deschis cu proprietar si remediation plan.
3. Model evaluation harness: rulat de doua ori; al doilea run nu trebuie sa arate regresie; daca o arata, finding documentat si remediat inainte de sustained operation declaration.
4. Privileged access review: completat de doua ori (initial + prima cadenta trimestriala).
5. Service health review: minutes inregistrate pentru cel putin 2 review-uri lunare consecutive.
6. Alert response drill: cel putin un alert declansat manual si traseul L1 → L2 verificat cu doua persoane; record in `evidence_pack`.

**Runbook verification requirement:**

- Cel putin 3 runbook-uri operationale executate de cineva altul decat autorul original.
- Execution records stocate in `evidence_pack`.

**Governance cadence proof:**

- `governance.change_log` trebuie sa contina minimum 10 entries din operatii post-deployment initial (nu din setup sau migrari initiale).
- `reconciliation_result` trebuie sa arate minimum 3 collection runs dupa baseline initial.

**Sustained operation declaration (artefact formal de inchidere):**

- Document de tip `operational_declaration`.
- Aprobat de `executive_sponsor`.
- Continut obligatoriu: toate loop-urile recurente executate de minim 2 ori, toate drill-urile completate, toate regression checks trecute sau issues documentate si remediate.
- Acest document gateaza orice comunicare publica de wave-2 readiness.

**Artefacte obligatorii:**

- `backup-restore-drill-evidence-cycle-1` si `cycle-2`.
- `load-test-results-v1` si `v2` cu comparison report.
- `model-evaluation-results-cycle-2` cu regression summary.
- `privileged-access-review-record-cycle-2`.
- `service-review-minutes-cycle-1` si `cycle-2`.
- `alert-response-drill-record`.
- `runbook-execution-records-pack` (≥3 runbooks executate de non-autori).
- `sustained-operation-declaration` (document formal aprobat).

---

**Regula de inchidere formala a celor 9 blocuri:**

- Blocurile 1–7 sunt inchise individual cand toate artefactele, drill-urile si criteriile de acceptanta ale epic-ului corespunzator sunt indeplinite simultan.
- Blocul 8 (Data Governance) este inchis cand classification matrix, redaction controls, access model si retention runbook sunt active si testate, iar declaratia de conformitate este semnata.
- Blocul 9 (Sustained Operation Proof) nu poate fi inchis inainte ca blocurile 1–8 sa fi produs cel putin un ciclu operational complet. El este intentionat ultimul.

**Interpretation rule for these supplemental workstreams:**

- Absenta lor nu invalideaza afirmatia ca planul actual este puternic pentru wave-1 foundation.
- Absenta lor invalideaza orice pretentie ca programul este deja complet enterprise-wide in sens maximal.
- Inchiderea formala a tuturor celor 9 blocuri, inclusiv Blocul 9 (Sustained Operation Proof), este conditia necesara si suficienta pentru a declara `complete enterprise operating model`.

## Content: Handoff Instructions for Execution Agents

Pentru orice task din acest plan, agentul executor trebuie sa primeasca cel putin urmatorul pachet de context:

- obiectivul task-ului si ID-ul lui din plan;
- epic, milestone si sprint de apartenenta;
- intrarile canonice aprobate relevante;
- active existente din repo care trebuie refolosite sau analizate;
- constrangeri de policy aplicabile;
- definitia de done si acceptanta task-ului.

Format minim al handoff-ului catre agent:

- Purpose: ce trebuie schimbat sau produs si de ce exista task-ul;
- In Scope: ce intra explicit in responsabilitatea lui;
- Out of Scope: ce nu are voie sa extinda;
- Inputs: documente, entitati, scripturi, configuratii si precedente relevante;
- Required Outputs: fisiere, artefacte, contracte, teste sau dovezi care trebuie sa rezulte;
- Constraints: reguli de adevar, policy, approval, compatibilitate si non-goals;
- Verification: teste, query-uri, review-uri si conditii de acceptare;
- Escalation Conditions: ce tip de ambiguitate sau conflict blocheaza si trebuie escaladat.

Reguli de handoff:

- daca task-ul modifica modelul de date, handoff-ul trebuie sa includa impactul asupra retrieval, ingestie si audit;
- daca task-ul modifica retrieval-ul, handoff-ul trebuie sa includa task types afectate si politica de token budget;
- daca task-ul modifica policy sau approvals, handoff-ul trebuie sa includa explicit deny paths, exceptions si audit expectations;
- daca task-ul vizeaza pilotul, handoff-ul trebuie sa includa toate dependintele shared service si acceptance checks.
- handoff-ul catre agentii de implementare trebuie sa reaminteasca explicit ca planul este read-only si ca singura schimbare permisa in document este actualizarea campului YAML `status` de la `in-progress` la `completed` dupa verificarea critica finala.

## Content: Detailed Handoff Templates by Epic Family

Template-urile de mai jos specializeaza formatul minim de handoff. Ele trebuie folosite atunci cand task-ul apartine unei familii de epice cu risc sau context specific. Daca exista conflict intre un template specializat si regulile generale audit-first din plan, regulile generale prevaleaza.

### Template for Data Model and Registry Change Work

Se aplica in principal la epicele `epic-2`, `epic-3` si la taskuri derivate din schema, migrari, taxonomii, query contracts si loadere.

Campuri obligatorii suplimentare:

- Registry Scope: tabele, scheme, taxonomii, entitati si relatii afectate;
- Canonical Inputs: documente, audit findings si reguli deja aprobate care justifica schimbarea;
- Query Impact: ce query-uri, retrieval flows, reconciliation checks sau audit surfaces sunt afectate;
- Migration Contract: ordine de aplicare, compatibilitate, seed data, rollback sau recovery path;
- Data Risk Notes: ce date pot deveni invalide, incomplete sau ambigue daca schimbarea este gresita.

Checklist minim pentru agent:

- demonstreaza de ce schimbarea nu poate fi exprimata doar prin JSONB sau logica procedurala ascunsa;
- arata impactul asupra retrieval, ingestie, audit si evidence provenance;
- include verificari pe exemple reale din clusterul curent si nu doar pe date sintetice;
- marcheaza orice necunoscuta de compatibilitate ca gap, nu ca asumptie tacita.

### Template for Recovery, Backup and Disaster Work

Se aplica in principal la `epic-8` si la orice task ce atinge backup, restore, export, retention operationala de recovery sau HA posture.

Campuri obligatorii suplimentare:

- Recovery Objective: RTO, RPO si postura aprobata de disponibilitate vizata de task;
- Recovery Scope: ce suprafete trebuie recuperate, in ce ordine si cu ce dependinte;
- Restore Evidence Plan: cum se demonstreaza ca restaurarea a reusit functional si nu doar procedural;
- Failure Scenario: ce incident sau mod de esec este simulat sau adresat;
- Residual Risk Statement: ce NU acopera exercitiul sau procedura respectiva.

Checklist minim pentru agent:

- nu considera backup-ul valid daca restore-ul nu este exercitat efectiv;
- valideaza atat baza de date cat si artefactele critice de audit sau configuratie unde este relevant;
- include un punct clar de decizie pentru single-instance accepted versus HA required;
- produce findings actionabile, nu doar confirmare binara de succes.

### Template for Supply Chain and Release Integrity Work

Se aplica in principal la `epic-10` si `epic-11`, plus taskuri de SBOM, scanning, provenance, release gates, rollback si promotion.

Campuri obligatorii suplimentare:

- Artifact Scope: ce pachete, imagini, build outputs sau release bundles sunt in scope;
- Provenance Inputs: de unde provin artefactele si ce surse third-party sunt implicate;
- Integrity Controls: ce scanari, semnari, attestations sau gates se aplica;
- Promotion Path: intre ce medii sau clase de release se deplaseaza schimbarea;
- Rollback Contract: ce se intampla daca verificarea post-release esueaza.

Checklist minim pentru agent:

- leaga fiecare artifact promovat de inventar, provenance si decizia de acceptare;
- nu marcheaza un artifact ca acceptabil fara rezultate de scanare sau fara review-ul politicii relevante;
- include rollback sau recovery pentru schimbarile care ating schema sau runtime critic;
- verifica faptul ca evidence chain-ul de release poate fi reconstruit ulterior pentru audit.

### Template for LLM Runtime and Model Governance Work

Se aplica in principal la `epic-12` si la taskuri despre model serving, model registry, evaluation harness, routing, fallback, latency, cost sau safety controls.

Campuri obligatorii suplimentare:

- Model Scope: modele, versiuni, task types si clase de workload afectate;
- Evaluation Basis: benchmark-uri, task sets, safety checks si criterii de selectie folosite;
- Runtime Guardrails: limite de latenta, cost, fallback, overload sau degradare;
- Safety Notes: riscuri de prompt behavior, red-team findings sau policy constraints relevante;
- Broker Interaction: cum afecteaza taskul retrieval broker, context broker sau action broker.

Checklist minim pentru agent:

- justifica model selection prin evaluare repetabila, nu prin preferinta operatorului;
- trateaza fallback-ul ca schimbare de comportament guvernata, nu ca mecanism opac de convenience;
- include impactul asupra task types suportate si asupra calitatii evidence-backed outputs;
- marcheaza orice lipsa de benchmark sau safety evidence ca blocaj de aprobare, nu ca detaliu optional.

### Template for Service Operations and Human Governance Work

Se aplica in principal la `epic-14`, dar si la taskuri despre RACI, on-call, support tiers, incident command, recurring reviews sau privileged access review.

Campuri obligatorii suplimentare:

- Ownership Scope: servicii, capabilitati, review loops sau accesuri privilegiate acoperite;
- Named Roles or Groups: cine raspunde efectiv, nu doar ce rol abstract exista in plan;
- Operational Cadence: frecventa review-urilor, on-call windows, escalation deadlines;
- Incident Path: traseul de escaladare si punctele de decizie pentru incidente sau exceptii;
- Governance Outputs: ce artefacte, minute, decizii sau registre trebuie sa rezulte recurent.

Checklist minim pentru agent:

- nu considera rolurile abstracte drept substitute pentru owneri reali;
- defineste L1/L2/L3 si escalation paths suficient de clar pentru executie sub presiune;
- leaga recurring reviews de input-uri si output-uri obligatorii, nu doar de intalniri recurente;
- marcheaza orice serviciu critic fara owner, on-call sau review cadence drept risc operational activ.

## Content: Verification Strategy

Strategia de verificare trebuie sa combine patru niveluri de control.

1. Verificare structurala.
   Se confirma ca documentele, schemele, contractele si pachetele respecta structura si validarile definite.

2. Verificare comportamentala.
   Se confirma ca registry-ul raspunde la query-uri relevante, collectorii ingereaza corect, retrieval-ul compune context util, action broker-ul blocheaza sau permite corect si pilotul ruleaza repetabil.

3. Verificare de guvernanta.
   Se confirma ca owners, approvals, exception paths si audit trails exista efectiv, nu doar declarativ.

4. Verificare operationala.
   Se confirma ca dashboard-urile, alertele, retention-ul si runbook-urile permit operarea sistemului in conditii reale.

Niciun epic nu se considera incheiat daca are doar livrabile create dar nu are verificarea corespunzatoare nivelului sau de risc.

## Content: Scope Boundaries and Anti-Patterns

Nu intra in wave-1:

- o platforma UI completa pentru tot ecosistemul;
- automatizare nelimitata a agentilor;
- introducerea unei noi baze de date de graf ca sistem core inainte sa existe nevoia demonstrata;
- ingestia tuturor surselor posibile inainte de stabilizarea modelului;
- pilot supra-dimensionat care combina prea multe necunoscute.

Anti-patterns explicite:

- registry folosit ca dump generic de JSON;
- retrieval care sare direct la vector search fara filtre structurale;
- aprobari in afara sistemului, nelegate de run records;
- reconciliere manuala, netrasabila;
- documente fara owner, fara identifiers sau fara status de aprobare;
- task-uri inchise pe baza de output generat, fara verificare.

## Content: Recommended First Files and Work Packages

Primele active existente care trebuie folosite ca baza de lucru sunt:

- blueprint-ul existent ca sursa de adevar arhitectural;
- audit_full.py ca referinta pentru colectare de fapte runtime si pentru vocabular de infrastructura;
- docker-compose si llm.yml din ai-infrastructure ca referinte pentru modul de ambalare a serviciilor infrastructurale;
- **main**.py, health.py si testele existente ca puncte de plecare pentru conventiile de CLI, health si testare.

Primele pachete de lucru recomandate dupa aprobarea acestui plan sunt:

1. extragerea ADR-urilor si definirea ownership matrix;
2. taxonomy + metadata schema + linking rules;
3. model logic registry + query contracts;
4. collector contracts + normalization catalog;
5. task type catalog + evidence pack contracts;
6. policy matrix + action contracts.

Aceasta ordine minimizeaza rework-ul si tine controlate dependintele dintre documentare, modelare, retrieval si executie.

## Content: Definition of Done at Program Level

Programul poate fi declarat implementat corect pentru wave-1 doar daca toate conditiile de mai jos sunt simultan adevarate:

- exista documente canonice standardizate pentru domeniile wave-1;
- registry-ul ruleaza si poate raspunde la query-uri esentiale cu provenance si state separation;
- colectarea si reconcilierea functioneaza pe sursele wave-1 cu freshness si drift severity definite;
- retrieval broker-ul produce evidence packs bounded pentru task-urile suportate;
- policy engine si action broker-ul intermediaza toate write path-urile suportate;
- pilotul este livrat prin fluxul guvernat si re-rulat repetabil;
- auditul, KPI-urile, alerting-ul si runbook-urile sunt active;
- review-ul de readiness aproba explicit extinderea catre wave-2.

Clarificare obligatorie de interpretare:

- aceasta definitie de done inchide fundatia programului pentru wave-1 si nu trebuie interpretata ca definitie de completitudine absoluta enterprise-wide;
- completitudinea enterprise maxima necesita inchiderea explicita a `Critical Enterprise Completeness Gap Register Beyond Wave-1 Foundation` si a workstream-urilor suplimentare aplicabile.

## Content: Effective Implementation Baseline for This Program

Acest addendum transforma planul din roadmap generic de program in plan de implementare efectiva pentru instanta concreta ceruta acum.

Constrangeri si decizii de executie pentru aceasta implementare:

- dezvoltarea initiala se face local pe macOS, pe masina curenta;
- versionarea sursei se face in Git, cu remote tinta: `https://github.com/neacisu/internal_CMDB.git`;
- runtime-ul PostgreSQL pentru system of record se ruleaza pe hostul `orchestrator.neanelu.ro`, accesat prin `ssh orchestrator`, ca serviciu containerizat dedicat gestionat prin Docker Compose, nu ca instalare directa in sistemul Debian;
- hostul `postgres-main` ramane in scope ca runtime PostgreSQL separat, existent si distinct functional de `internalCMDB`; auditul de runtime din 2026-03-08 a confirmat ca este reachable prin SSH, ruleaza `postgresql.service`, `postgresql@18-main.service` si `postgres-exporter.service`, are cron-uri active de `pg_dump` sub `/opt/cerniq/scripts/` si nu ruleaza Docker;
- decizia de containerizare este obligatorie pentru aceasta prima instanta deoarece pe `orchestrator` Docker are deja `DockerRootDir=/mnt/HC_Volume_105014654/docker`, adica imaginile si cache-ul sunt mutate de pe volumul principal pe volumul separat, iar PostgreSQL nu exista inca nici ca serviciu systemd activ, nici ca container existent;
- storage-ul persistent pentru runtime-ul PostgreSQL trebuie plasat pe volumul montat la `/mnt/HC_Volume_105014654`, prin bind mounts explicite dedicate pentru date, backup-uri si exporturi, nu prin dependenta implicita doar de Docker root si nu prin volume anonime;
- politica de expunere pentru noul PostgreSQL trebuie sa urmeze modelul enterprise existent al clusterului pentru acces extern la baze de date: target-state-ul este ca Traefik shared de pe `orchestrator` sa furnizeze punctul unic de intrare TCP pe portul standard `5432`, iar rutarea catre backend sa se faca prin SNI pe hostname dedicat, dupa validarea live a configuratiei si a probelor de conectivitate;
- referinta de non-conflict validata la planificare este ca exista deja hostname-urile `postgres.neanelu.ro` si `postgres.orchestrator.neanelu.ro` care rezolva la `77.42.76.185`, iar modelul istoric Traefik validat in configuratiile de backup a folosit `HostSNI(postgres.neanelu.ro)` pentru a route-ui traficul catre backend-ul `10.0.1.107:5432` al `postgres-main`;
- decizia pentru wave-1 este ca noul runtime `internalCMDB` sa fie expus extern prin `postgres.orchestrator.neanelu.ro:5432`, prin Traefik TCP/SNI, in timp ce backend-ul local al containerului ramane separat pe un port host non-standard sau pe loopback, pentru a evita coliziunea directa cu alte backend-uri PostgreSQL;
- auditul de trust din 2026-03-08 a observat ca atat `postgres.neanelu.ro:5432`, cat si `postgres.orchestrator.neanelu.ro:5432` raspund in prezent cu `connection refused`, deci conectarea directa pe hostname extern trebuie tratata ca stare tinta dupa activarea/validarea rutarii TCP in Traefik, nu ca stare deja operationala;
- modelul explicit de conectare pentru aplicatia locala de pe Mac ramane impartit intre target-state si fallback: pentru `internalCMDB`, target-state-ul este folosirea directa a `postgres.orchestrator.neanelu.ro:5432` dupa activarea rutei dedicate; pentru runtime-ul PostgreSQL al aplicatiilor existente, suprafata separata ramane `postgres.neanelu.ro`; pana la validarea rutarii publice pe `:5432`, tunelul SSH ramane mecanismul operational real pentru administrare si testare;
- pentru ca rutarea SNI sa fie determinista, conexiunea client trebuie sa foloseasca TLS compatibil cu modelul Traefik TCP deja validat in cluster, iar reactivarea sau definirea entrypoint-ului TCP `postgres` in Traefik shared devine parte explicita din implementare;
- baza de date tinta se numeste `internalCMDB`;
- versiunea PostgreSQL trebuie sa fie ultima versiune stabila generala disponibila la momentul executiei, validata in ziua instalarii, iar imaginea Docker folosita trebuie pin-uita explicit la versiunea aprobata, fara folosirea unui tag flotant de tip `latest` in productie;
- bootstrap-ul initial accepta temporar acces administrativ fara parola pentru rolul `postgres`, strict ca exceptie de bootstrap si strict pana la terminarea etapei de seed si validare initiala;
- cerinta exprimata ca `RLS pe toate coloanele` se traduce tehnic astfel: Row Level Security activat pe toate tabelele de business, iar restrictiile la nivel de coloane se implementeaza prin grants, views si schema separation, deoarece PostgreSQL nu implementeaza RLS direct per coloana;
- scripturile existente din repo si subproiecte trebuie tratate ca puncte de pornire pentru colectare si normalizare, nu ca sursa finala neadaptata pentru ingestie enterprise-grade;
- suprafata de operare pentru PostgreSQL trebuie sa includa explicit fisier Compose dedicat, healthcheck, restart policy, bind mounts versionate in plan si expunere de retea minim necesara pentru bootstrap si pentru runtime-ul ulterior.

## Content: Exact Enterprise Delivery Track for Effective Implementation

Acest track completeaza planul de program de mai sus si defineste implementarea efectiva a primei instante operationale.

```yaml
effective_delivery_track:
  track_id: effective-wave-1-internal-cmdb
  objective: >-
    Implementarea efectiva a primei instante a platformei interne sub forma
    internalCMDB, cu dezvoltare locala pe macOS, versionare in Git, PostgreSQL
    operational pe orchestrator, ingestie initiala a infrastructurii reale din
    activele si scripturile existente in repo, retrieval brokerizat,
    action governance explicita, pilot application flow complet si
    observabilitate operationala pentru wave-1.
  delivery_honesty:
    current_truthful_status: expanded-enterprise-draft-for-implementation-review
    no_absolute_completeness_claim: true
    interpretation_rule: materially-complete-for-wave-1-foundation-but-still-subject-to-reviewed-live-adjustments
    completion_claim_blockers:
      - approval-candidate-kpi-thresholds-still-require-formal-approval
      - pilot-application-is-not-yet-selected-and-approved
      - epic-15-data-governance-and-compliance-controls-not-yet-defined-or-approved
      - epic-16-sustained-operation-proof-requires-second-cycle-evidence-not-yet-available
      - rto-rpo-thresholds-and-ha-posture-require-explicit-formal-approval-document
      - postgresql-on-orchestrator-not-yet-deployed-internalcmdb-schema-not-yet-migrated
      - first-backfill-not-yet-executed-registry-contains-no-live-data
    live_validation_record:
      generated_at_utc: "2026-03-08T11:30:00Z"
      validated_by: "Alex Neacsu"
      ssh_connectivity:
        total: 12
        ok: 11
        fail: 1
        failed_hosts:
          - host: imac
            detail: "ssh: connect to host 192.168.100.9 port 22: Operation timed out"
        reachable_hosts:
          [
            orchestrator,
            postgres-main,
            hz.62,
            hz.113,
            hz.118,
            hz.123,
            hz.157,
            hz.164,
            hz.215,
            hz.223,
            hz.247,
          ]
      runtime_posture_confirmed:
        orchestrator:
          {
            os: "Debian GNU/Linux 13 (trixie)",
            docker: true,
            containers: 21,
            key_containers:
              [
                traefik,
                prometheus,
                grafana,
                loki,
                tempo,
                otel-collector,
                openbao,
                zitadel,
                roundcube,
                llm-guard,
                redis-shared,
                watchtower,
                pve-exporter,
                cloudbeaver,
              ],
          }
        postgres_main:
          {
            os: "Ubuntu 24.04 LTS",
            docker: false,
            postgres_services:
              [
                postgresql.service,
                "postgresql@18-main.service",
                postgres-exporter.service,
              ],
            cron_backups: true,
          }
        hz_113:
          {
            os: "Ubuntu 24.04.4 LTS",
            docker: true,
            containers: 7,
            ai_runtime:
              [vllm-qwen-14b, vllm-qwq-32b, open-webui, openbao-agent-llm],
          }
        hz_62:
          {
            os: "Ubuntu 24.04.4 LTS",
            docker: true,
            containers: 4,
            role: [ollama-embed, cadvisor, node-exporter, nvidia-gpu-exporter],
          }
        hz_123:
          {
            os: "Ubuntu 24.04.3 LTS",
            docker: true,
            containers: 8,
            stack: flowxify,
            services: [n8n, activepieces, postgres-17, redis],
          }
        hz_164:
          {
            os: "Ubuntu 24.04.3 LTS",
            docker: true,
            containers: 57,
            lets_encrypt_certs: 6,
          }
        hz_118:
          {
            os: "Debian GNU/Linux 13 (trixie)",
            docker: false,
            role: standalone_proxmox,
          }
        hz_157:
          {
            os: "Debian GNU/Linux 11 (bullseye)",
            docker: false,
            role: standalone_proxmox,
          }
        hz_215:
          {
            os: "Debian GNU/Linux 13 (trixie)",
            docker: false,
            role: proxmox_cluster_member,
          }
        hz_223:
          {
            os: "Debian GNU/Linux 13 (trixie)",
            docker: false,
            role: proxmox_cluster_member,
          }
        hz_247:
          {
            os: "Debian GNU/Linux 13 (trixie)",
            docker: false,
            role: proxmox_cluster_member,
          }
      trust_surface_confirmed:
        postgres_neanelu_ro_5432: "connection refused - not yet routed through Traefik"
        postgres_orchestrator_neanelu_ro_5432: "connection refused - internalCMDB PostgreSQL not yet deployed"
        hz_164_lets_encrypt_cert_paths: 6
        all_hosts_secret_paths_scanned: true
  implementation_topology:
    development_host:
      type: local-macos-workstation
      purpose: source-authoring-migrations-testing-and-adapter-development
    source_control:
      vcs: git
      remote_url: https://github.com/neacisu/internal_CMDB.git
      branching_rule: trunk-based-with-short-lived-feature-branches
    observed_inventory_scope:
      approved_hosts:
        - orchestrator
        - postgres-main
        - imac
        - hz.62
        - hz.113
        - hz.118
        - hz.123
        - hz.157
        - hz.164
        - hz.215
        - hz.223
        - hz.247
      ssh_reachable_at_2026_03_08:
        - orchestrator
        - postgres-main
        - hz.62
        - hz.113
        - hz.118
        - hz.123
        - hz.157
        - hz.164
        - hz.215
        - hz.223
        - hz.247
      current_reachability_gaps:
        - host: imac
          observation: ssh-port-22-connection-refused
    target_database_host:
      ssh_alias: orchestrator
      fqdn: orchestrator.neanelu.ro
      os: debian-linux
      live_observation:
        docker_root_dir: /mnt/HC_Volume_105014654/docker
        root_filesystem_free_space_context: separate-data-volume-already-in-use-for-docker
        postgres_runtime_present: none-detected-at-planning-time
      persistence_mount: /mnt/HC_Volume_105014654
      persistence_requirement: postgresql-bind-mounted-data-backups-and-exports-must-live-on-mounted-volume
    existing_application_database_host:
      host_code: postgres-main
      ssh_alias: postgres-main
      observed_hostname: postgres-main
      observed_fqdn: null
      external_service_fqdn: postgres.neanelu.ro
      identifier_honesty_rule: host_code-and-ssh_alias-are-not-fqdn-and-must-not-be-reused-as-exposure-hostnames-without-live-dns-or-hostname-evidence
      role: existing-postgresql-runtime-for-application-workloads
      live_observation:
        os: ubuntu-24-04-lts
        docker_present: false
        postgres_runtime_present:
          - postgresql.service
          - postgresql@18-main.service
          - postgres-exporter.service
        backup_indicators:
          - /etc/cron.d/cerniq-pg-dump
          - /etc/cron.d/ct107-cerniq-pg-dump
    target_database:
      name: internalCMDB
      engine: postgresql-container-image-pinned-to-latest-stable-approved-at-execution-date
      deployment_model: dedicated-docker-compose-service
      compose_project_scope: internal-cmdb-postgres
      data_path: /mnt/HC_Volume_105014654/postgresql/internalcmdb/data
      backup_path: /mnt/HC_Volume_105014654/postgresql/internalcmdb/backups
      export_path: /mnt/HC_Volume_105014654/postgresql/internalcmdb/exports
      exposure_policy: target-state-external-access-via-shared-traefik-tcp-sni-on-5432-after-live-validation
      preferred_access_model: external-fqdn-via-traefik-tcp-router-after-route-activation-and-live-probe-success
      development_access_model: use-ssh-tunnel-or-controlled-backend-port-until-postgres-orchestrator-neanelu-ro-5432-is-live
      backend_host_port_policy: publish-container-on-nonstandard-loopback-or-controlled-host-port-behind-traefik
      backend_reserved_port: 55432
      external_fqdn: postgres.orchestrator.neanelu.ro
      shared_traefik_tcp_entrypoint: postgres
      current_external_connectivity_state:
        postgres_neanelu_ro_5432: connection-refused-at-2026-03-08-trust-audit
        postgres_orchestrator_neanelu_ro_5432: connection-refused-at-2026-03-08-trust-audit
      coexistence_rule: internalcmdb-route-must-not-impact-existing-postgres-main-surface-on-postgres-neanelu-ro
      bootstrap_admin_role: postgres
      bootstrap_auth_mode: temporary-no-password-exception
      bootstrap_exception_rule: remove-or-restrict-after-initial-bootstrap-phase
    security_translation:
      requested_rule: rls-on-all-columns
      actual_implementation_rule: rls-on-all-business-tables-plus-column-restriction-via-views-grants-and-schema-boundaries
      observed_ssh_posture_gap: root-login-and-passwordauthentication-still-enabled-on-audited-ssh-reachable-hosts-at-2026-03-08
    context_broker:
      model: policy-controlled-context-broker
      input_order: canonical-documents-then-registry-then-observed-state-then-policy-then-semantic-complements
      output_contract: bounded-evidence-pack-with-provenance-gaps-and-selection-rationale
    retrieval_broker:
      deterministic_layers:
        - exact-lookup
        - metadata-filtering
        - lexical-search
      semantic_layers:
        - embeddings-on-prefiltered-document-chunks
        - reranking
      bounded_context_rule: no-unfiltered-global-semantic-retrieval
    action_broker:
      model: all-write-paths-mediated-and-audited
      approval_contract: approval-record-plus-scope-plus-expiry-plus-post-execution-verification
      deny_by_default: true
    pilot_application_artifacts:
      mandatory_documents:
        - research-dossier
        - application-definition-pack
        - verification-specification
        - evidence-map
      execution_rule: pilot-is-invalid-if-any-mandatory-artifact-is-missing-or-unapproved
    observability_and_audit:
      dashboards_required: true
      alerting_required: true
      retention_policy_required: true
      runbooks_required: true
      kpi_tracking_required: true
      shared_operational_surface: grafana-prometheus-loki-shared-on-orchestrator
      dashboard_delivery_model: dashboards-and-alert-consumption-live-in-shared-grafana-while-definitions-remain-canonical-in-git-and-plan
      signal_classes_required:
        - metrics
        - logs
        - derived-health-queries
        - audit-events
      runbook_storage_model: canonical-runbooks-versioned-in-git-with-links-from-grafana-and-alerts
      retention_enforcement_surfaces:
        - internalcmdb-policy-controlled-records
        - collection-output-paths
        - evidence-pack-and-agent-run-records
        - shared-log-surfaces-where-applicable
  effective_epics:
    - id: impl-epic-1
      status: in-progress
      name: local-workspace-and-repository-bootstrap
      objective: establish the local engineering baseline and bind it to the dedicated Git repository
      outcome: reproducible local development workspace linked to the internal_CMDB repository
    - id: impl-epic-2
      status: in-progress
      name: orchestrator-postgresql-foundation
      objective: provision the database host runtime, storage layout and dedicated containerized PostgreSQL service on orchestrator
      outcome: running PostgreSQL container stack backed by bind-mounted paths on the mounted persistent volume
    - id: impl-epic-3
      status: in-progress
      name: internalcmdb-enterprise-schema-and-taxonomy
      objective: design and implement the full database structure, taxonomies and migrations for internalCMDB
      outcome: enterprise-grade schema, migration chain and taxonomy reference model
    - id: impl-epic-4
      status: in-progress
      name: security-model-roles-and-access-boundaries
      objective: implement bootstrap access, table-level RLS, column exposure controls and operational access patterns
      outcome: enforceable access model compatible with the blueprint and the requested bootstrap posture
    - id: impl-epic-5
      status: in-progress
      name: discovery-adapters-normalization-and-initial-backfill
      objective: adapt or create local scripts that discover real infrastructure facts and write normalized records into internalCMDB
      outcome: first full backfill of real infrastructure data into the registry
    - id: impl-epic-6
      status: in-progress
      name: validation-reconciliation-and-operational-readiness
      objective: validate data quality, verify taxonomy coverage, reconcile observed facts and prepare the platform for continued evolution
      outcome: auditable and queryable first production-capable registry baseline
    - id: impl-epic-7
      status: in-progress
      name: context-and-retrieval-broker-foundation
      objective: implement the bounded context assembly path, document chunking and evidence pack generation required by the blueprint
      outcome: deterministic-plus-semantic retrieval working through policy-controlled broker contracts
    - id: impl-epic-8
      status: in-progress
      name: action-broker-agent-audit-and-prompt-governance
      objective: operationalize mediated write paths, prompt template governance and auditable agent run records
      outcome: control plane foundation that can approve deny record and explain agent actions
    - id: impl-epic-9
      status: in-progress
      name: pilot-application-definition-and-governed-delivery
      objective: create the first complete pilot artifact set and validate the governed application delivery flow end-to-end
      outcome: approved pilot package with research dossier application definition verification spec and evidence map exercised in practice
    - id: impl-epic-10
      status: in-progress
      name: observability-retention-runbooks-and-wave-1-readiness
      objective: make the platform observable auditable operable and reviewable for enterprise rollout decisions
      outcome: dashboards alerts retention rules runbooks KPI baselines and shared-observability operating paths active for wave-1
  effective_milestones:
    - id: impl-m1
      status: in-progress
      epic_id: impl-epic-1
      name: repository-and-local-toolchain-ready
      acceptance: local repo initialized or linked to remote, Python toolchain validated, migration tooling selected
    - id: impl-m2
      status: in-progress
      epic_id: impl-epic-2
      name: orchestrator-storage-and-postgresql-ready
      acceptance: PostgreSQL container stack deployed on orchestrator, bind-mounted data paths persisted on target volume, coexistence with `postgres-main` is evidenced, and Traefik routing for `postgres.orchestrator.neanelu.ro:5432` is either validated live without affecting `postgres.neanelu.ro` or blocked with an explicit evidence-backed gap record that preserves safe fallback access
    - id: impl-m3
      status: in-progress
      epic_id: impl-epic-3
      name: logical-data-model-approved
      acceptance: entity model, taxonomy hierarchy and naming conventions frozen for wave-1
    - id: impl-m4
      status: in-progress
      epic_id: impl-epic-3
      name: migration-chain-v1-ready
      acceptance: initial schema migrations apply cleanly from empty database to current head
    - id: impl-m5
      status: in-progress
      epic_id: impl-epic-4
      name: security-controls-v1-active
      acceptance: business tables protected with RLS and column exposure restrictions implemented
    - id: impl-m6
      status: in-progress
      epic_id: impl-epic-5
      name: source-adapters-defined
      acceptance: extractor contracts agreed for all wave-1 discovery sources
    - id: impl-m7
      status: in-progress
      epic_id: impl-epic-5
      name: normalized-ingestion-live
      acceptance: local scripts can write normalized records into internalCMDB without manual SQL intervention
    - id: impl-m8
      status: in-progress
      epic_id: impl-epic-5
      name: first-full-backfill-complete
      acceptance: all currently reachable machines and key services are represented in the registry, while in-scope but unreachable assets such as `imac` are recorded explicitly with observation-status and gap context
    - id: impl-m9
      status: in-progress
      epic_id: impl-epic-6
      name: data-quality-and-reconciliation-reviewed
      acceptance: duplicates, missing bindings and inconsistent taxonomies are reviewed and corrected
    - id: impl-m10
      status: in-progress
      epic_id: impl-epic-6
      name: operational-baseline-approved
      acceptance: internalCMDB can be used as the first authoritative operational registry baseline for continued platform work
    - id: impl-m11
      status: in-progress
      epic_id: impl-epic-7
      name: retrieval-objects-and-chunking-live
      acceptance: document chunks embeddings and evidence-pack persistence model are implemented and linked to canonical document versions
    - id: impl-m12
      status: in-progress
      epic_id: impl-epic-7
      name: context-broker-produces-bounded-evidence-packs
      acceptance: supported task types receive compact provenance-backed evidence packs using deterministic-first retrieval and policy filters
    - id: impl-m13
      status: in-progress
      epic_id: impl-epic-8
      name: action-broker-and-approval-enforcement-active
      acceptance: no supported write path bypasses mediated action requests approvals and audit records
    - id: impl-m14
      status: in-progress
      epic_id: impl-epic-8
      name: prompt-template-and-agent-run-ledger-active
      acceptance: prompt templates are versioned and every material agent run produces run records and evidence bindings
    - id: impl-m15
      status: in-progress
      epic_id: impl-epic-9
      name: pilot-research-and-definition-pack-approved
      acceptance: research dossier application definition pack verification specification and evidence map exist and are approved for the selected pilot
    - id: impl-m16
      status: in-progress
      epic_id: impl-epic-9
      name: governed-pilot-flow-verified
      acceptance: the pilot runs through brokered context, approval-gated actions and post-run verification without hidden manual bypasses
    - id: impl-m17
      status: in-progress
      epic_id: impl-epic-10
      name: operational-observability-and-retention-active
      acceptance: dashboards alerts retention and audit review workflows are active for registry discovery retrieval and agent control surfaces
    - id: impl-m18
      status: in-progress
      epic_id: impl-epic-10
      name: runbooks-and-kpi-baseline-approved
      acceptance: runbooks exist for critical flows and KPI review establishes a defensible wave-1 readiness baseline
    - id: impl-m19
      status: in-progress
      epic_id: impl-epic-10
      name: shared-signal-contracts-and-instrumentation-live
      acceptance: registry discovery retrieval approval and agent-run surfaces emit approved signals consumable through shared observability on orchestrator
    - id: impl-m20
      status: in-progress
      epic_id: impl-epic-10
      name: grafana-shared-dashboards-and-alert-routing-tested
      acceptance: shared grafana exposes actionable dashboards and tested alert routing for critical wave-1 failure modes and kpi views
    - id: impl-m21
      status: in-progress
      epic_id: impl-epic-10
      name: retention-enforcement-runbook-linkage-and-observability-drill-approved
      acceptance: retention enforcement runbook linkage and at least one observability drill are validated on live or controlled wave-1 surfaces
  effective_sprints:
    - id: impl-sprint-1
      status: in-progress
      duration: 1-week
      goal: local bootstrap and repository binding
      milestone_ids: [impl-m1]
    - id: impl-sprint-2
      status: in-progress
      duration: 1-week
      goal: orchestrator Docker Compose PostgreSQL provisioning and persistent storage setup
      milestone_ids: [impl-m2]
    - id: impl-sprint-3
      status: in-progress
      duration: 2-weeks
      goal: schema design taxonomy definition and migration authoring
      milestone_ids: [impl-m3, impl-m4]
    - id: impl-sprint-4
      status: in-progress
      duration: 1-week
      goal: access model RLS and view-based exposure controls
      milestone_ids: [impl-m5]
    - id: impl-sprint-5
      status: in-progress
      duration: 2-weeks
      goal: extractor adaptation normalization and first ingestion
      milestone_ids: [impl-m6, impl-m7]
    - id: impl-sprint-6
      status: in-progress
      duration: 1-to-2-weeks
      goal: full backfill validation reconciliation and operational sign-off
      milestone_ids: [impl-m8, impl-m9, impl-m10]
    - id: impl-sprint-7
      status: in-progress
      duration: 2-weeks
      goal: retrieval object model chunking embeddings and bounded context brokerage
      milestone_ids: [impl-m11, impl-m12]
    - id: impl-sprint-8
      status: in-progress
      duration: 1-to-2-weeks
      goal: mediated write paths prompt governance and auditable agent runs
      milestone_ids: [impl-m13, impl-m14]
    - id: impl-sprint-9
      status: in-progress
      duration: 2-weeks
      goal: pilot artifact pack and governed end-to-end application flow
      milestone_ids: [impl-m15, impl-m16]
    - id: impl-sprint-10
      status: in-progress
      duration: 1-to-2-weeks
      goal: operational observability retention runbooks and KPI baseline
      milestone_ids: [impl-m17, impl-m18]
    - id: impl-sprint-11
      status: in-progress
      duration: 1-to-2-weeks
      goal: implement shared observability signal contracts and instrumentation for critical wave-1 surfaces
      milestone_ids: [impl-m19]
    - id: impl-sprint-12
      status: in-progress
      duration: 1-to-2-weeks
      goal: deliver shared grafana dashboards tested alert routing and kpi or slo operational views
      milestone_ids: [impl-m20]
    - id: impl-sprint-13
      status: in-progress
      duration: 1-to-2-weeks
      goal: validate retention enforcement runbook linkage and observability drill readiness
      milestone_ids: [impl-m21]
  effective_tasks:
    - id: impl-t-001
      status: in-progress
      sprint_id: impl-sprint-1
      epic_id: impl-epic-1
      name: initialize-or-link-local-repository-to-internal_cmdb-remote
      deliverable: local working tree bound to github remote and documented bootstrap steps
    - id: impl-t-002
      status: in-progress
      sprint_id: impl-sprint-1
      epic_id: impl-epic-1
      name: define-local-project-layout-for-schema-migrations-loaders-and-taxonomies
      deliverable: agreed directory layout for migrations models taxonomies loaders and tests
    - id: impl-t-003
      status: in-progress
      sprint_id: impl-sprint-1
      epic_id: impl-epic-1
      name: select-and-bootstrap-migration-framework
      deliverable: migration tool integrated locally with repeatable upgrade and downgrade commands
    - id: impl-t-004
      status: in-progress
      sprint_id: impl-sprint-1
      epic_id: impl-epic-1
      name: define-environment-configuration-model
      deliverable: local and remote configuration contract for connection strings paths and execution modes
    - id: impl-t-005
      status: in-progress
      sprint_id: impl-sprint-2
      epic_id: impl-epic-2
      name: validate-orchestrator-storage-layout-on-mounted-volume
      deliverable: approved bind-mount layout under mounted volume for PostgreSQL data backups and exports
    - id: impl-t-006
      status: in-progress
      sprint_id: impl-sprint-2
      epic_id: impl-epic-2
      name: author-and-stage-dedicated-docker-compose-stack-for-postgresql-on-orchestrator
      deliverable: dedicated Compose stack with pinned PostgreSQL image, healthcheck, restart policy, explicit bind mounts and backend exposure on a non-standard host port suitable for Traefik TCP forwarding
    - id: impl-t-007
      status: in-progress
      sprint_id: impl-sprint-2
      epic_id: impl-epic-2
      name: create-persistent-bind-mount-layout-and-launch-postgresql-container
      deliverable: active PostgreSQL container storing data backups and exports on the target mounted volume, with backend host exposure bound on the approved non-standard port for Traefik TCP forwarding
    - id: impl-t-008
      status: in-progress
      sprint_id: impl-sprint-2
      epic_id: impl-epic-2
      name: create-internalcmdb-database-and-bootstrap-admin-access-in-containerized-runtime
      deliverable: database internalCMDB created inside the dedicated PostgreSQL runtime with temporary bootstrap administrative access as requested
    - id: impl-t-008a
      status: in-progress
      sprint_id: impl-sprint-2
      epic_id: impl-epic-2
      name: verify-port-and-routing-non-conflict-with-traefik-and-existing-postgresql-dependencies
      deliverable: read-only validation record that distinguishes target-state from current-state, proves whether shared Traefik TCP routing separates `postgres.neanelu.ro` from `postgres.orchestrator.neanelu.ro`, captures the current 2026-03-08 `connection refused` findings on both public `:5432` endpoints, and documents non-collision criteria for existing PostgreSQL consumers such as ZITADEL backend connectivity
    - id: impl-t-008b
      status: in-progress
      sprint_id: impl-sprint-2
      epic_id: impl-epic-2
      name: document-and-test-external-macos-connection-path-via-traefik-tcp
      deliverable: staged developer connection recipe that uses fallback SSH tunneling or approved backend access until `postgres.orchestrator.neanelu.ro:5432` is live, plus the direct TLS connection recipe to be validated once the Traefik TCP route succeeds
    - id: impl-t-008c
      status: in-progress
      sprint_id: impl-sprint-2
      epic_id: impl-epic-2
      name: restore-or-add-shared-traefik-postgres-tcp-entrypoint-and-sni-route
      deliverable: Traefik change set and validation evidence that activate TCP entrypoint `postgres` on `:5432` for `postgres.orchestrator.neanelu.ro` only when live probes succeed and preserve the existing `postgres.neanelu.ro` surface backed by `postgres-main`
    - id: impl-t-009
      status: in-progress
      sprint_id: impl-sprint-3
      epic_id: impl-epic-3
      name: derive-enterprise-taxonomy-from-blueprint-and-current-infrastructure
      deliverable: taxonomy hierarchy for infrastructure services ownership states evidence and relations
    - id: impl-t-010
      status: in-progress
      sprint_id: impl-sprint-3
      epic_id: impl-epic-3
      name: define-core-entity-model-for-hosts-services-instances-networks-storage-and-applications
      deliverable: logical entity model with identifiers relationships lifecycle and provenance fields
    - id: impl-t-011
      status: in-progress
      sprint_id: impl-sprint-3
      epic_id: impl-epic-3
      name: define-supporting-reference-tables-and-enumeration-taxonomies
      deliverable: reference taxonomy tables and controlled vocabularies for normalized ingestion
    - id: impl-t-012
      status: in-progress
      sprint_id: impl-sprint-3
      epic_id: impl-epic-3
      name: author-initial-schema-migrations-for-all-wave-1-tables
      deliverable: first complete migration chain for schemas tables indexes constraints comments and seed reference data
    - id: impl-t-013
      status: in-progress
      sprint_id: impl-sprint-3
      epic_id: impl-epic-3
      name: create-db-comments-and-data-dictionary-coverage
      deliverable: database comments and accompanying dictionary for every core table and column
    - id: impl-t-014
      status: in-progress
      sprint_id: impl-sprint-4
      epic_id: impl-epic-4
      name: classify-business-tables-and-enable-rls-on-each
      deliverable: RLS enabled on every business table that stores operational records
    - id: impl-t-015
      status: in-progress
      sprint_id: impl-sprint-4
      epic_id: impl-epic-4
      name: implement-view-based-column-exposure-model
      deliverable: restricted views and grants for sensitive columns and role-specific read surfaces
    - id: impl-t-016
      status: in-progress
      sprint_id: impl-sprint-4
      epic_id: impl-epic-4
      name: define-bootstrap-security-exception-and-hardening-followup
      deliverable: explicit record of temporary no-password bootstrap posture, current audited SSH posture gaps (`permitrootlogin yes` and `passwordauthentication yes` on audited reachable hosts), and mandatory hardening task list
    - id: impl-t-017
      status: in-progress
      sprint_id: impl-sprint-5
      epic_id: impl-epic-5
      name: inventory-existing-scripts-that-can-feed-discovery
      deliverable: source inventory covering local scripts and subproject scripts reusable for extraction
    - id: impl-t-018
      status: in-progress
      sprint_id: impl-sprint-5
      epic_id: impl-epic-5
      name: define-normalization-contracts-between-script-output-and-database-schema
      deliverable: canonical loader contract mapping raw script fields to target tables and taxonomies
    - id: impl-t-019
      status: in-progress
      sprint_id: impl-sprint-5
      epic_id: impl-epic-5
      name: adapt-audit_full-and-related-auditors-into-loader-compatible-producers
      deliverable: normalized machine facts exported in a structured format ready for database loading
    - id: impl-t-020
      status: in-progress
      sprint_id: impl-sprint-5
      epic_id: impl-epic-5
      name: implement-local-loader-scripts-for-upsert-into-internalcmdb
      deliverable: local loader scripts that create or update normalized registry records
    - id: impl-t-021
      status: in-progress
      sprint_id: impl-sprint-5
      epic_id: impl-epic-5
      name: implement-provenance-capture-on-every-ingested-record
      deliverable: source timestamp collector identifier and execution context persisted with each load batch
    - id: impl-t-022
      status: in-progress
      sprint_id: impl-sprint-5
      epic_id: impl-epic-5
      name: run-first-targeted-ingestion-for-priority-machines
      deliverable: first verified subset of `orchestrator`, `postgres-main` and directly related machines written into internalCMDB with provenance and role separation preserved
    - id: impl-t-023
      status: in-progress
      sprint_id: impl-sprint-6
      epic_id: impl-epic-5
      name: execute-full-wave-1-backfill-of-reachable-machines-and-core-services
      deliverable: first complete inventory load for all currently reachable infrastructure assets in scope, plus explicit placeholder facts and gap records for in-scope assets that are currently unreachable
    - id: impl-t-024
      status: in-progress
      sprint_id: impl-sprint-6
      epic_id: impl-epic-6
      name: validate-row-counts-relations-nullability-and-taxonomy-coverage
      deliverable: data quality report with coverage gaps duplicates and relation anomalies
    - id: impl-t-025
      status: in-progress
      sprint_id: impl-sprint-6
      epic_id: impl-epic-6
      name: reconcile-observed-facts-with-blueprint-driven-canonical-model
      deliverable: reconciliation report highlighting mismatches missing bindings and taxonomy gaps
    - id: impl-t-026
      status: in-progress
      sprint_id: impl-sprint-6
      epic_id: impl-epic-6
      name: create-operational-query-pack-for-internalcmdb
      deliverable: curated SQL and CLI query pack for hosts services dependencies evidence and ownership lookups
    - id: impl-t-027
      status: in-progress
      sprint_id: impl-sprint-6
      epic_id: impl-epic-6
      name: document-next-hardening-step-for-postgres-authentication
      deliverable: explicit post-bootstrap hardening plan for passwords auth methods roles and network exposure
    - id: impl-t-028
      status: in-progress
      sprint_id: impl-sprint-6
      epic_id: impl-epic-6
      name: approve-internalcmdb-as-wave-1-registry-baseline
      deliverable: sign-off record that the first operational baseline is usable for continued platform build-out
    - id: impl-t-029
      status: in-progress
      sprint_id: impl-sprint-7
      epic_id: impl-epic-7
      name: author-context-broker-contract-for-supported-task-types
      deliverable: formal contract describing task classification, scope filters, evidence composition order and bounded output schema
    - id: impl-t-030
      status: in-progress
      sprint_id: impl-sprint-7
      epic_id: impl-epic-7
      name: implement-document-chunking-and-version-bound-indexing
      deliverable: repeatable pipeline that creates document chunks tied strictly to canonical document versions and hashes
    - id: impl-t-031
      status: in-progress
      sprint_id: impl-sprint-7
      epic_id: impl-epic-7
      name: implement-local-embedding-pipeline-and-chunk-vector-storage
      deliverable: local embedding generation with model versioning and persisted vectors for approved chunks only
    - id: impl-t-032
      status: in-progress
      sprint_id: impl-sprint-7
      epic_id: impl-epic-7
      name: implement-evidence-pack-generation-and-selection-rationale-capture
      deliverable: bounded evidence packs with mandatory, recommended and excluded item classes plus explicit inclusion rationale
    - id: impl-t-033
      status: in-progress
      sprint_id: impl-sprint-7
      epic_id: impl-epic-7
      name: validate-retrieval-ordering-deterministic-before-semantic
      deliverable: verification record proving exact lookup and metadata filtering precede lexical and semantic retrieval in supported flows
    - id: impl-t-034
      status: in-progress
      sprint_id: impl-sprint-8
      epic_id: impl-epic-8
      name: define-action-broker-risk-classes-and-deny-paths
      deliverable: action-class matrix covering read-only analysis repo writes bounded runtime changes and high-risk infrastructure actions
    - id: impl-t-035
      status: in-progress
      sprint_id: impl-sprint-8
      epic_id: impl-epic-8
      name: implement-approval-bound-action-request-ledger
      deliverable: persisted action requests linked to approvals scope requested changes status and execution outcome
    - id: impl-t-036
      status: in-progress
      sprint_id: impl-sprint-8
      epic_id: impl-epic-8
      name: implement-prompt-template-registry-with-versioning-and-policy-binding
      deliverable: governed prompt template registry tied to task type policy and canonical source versions
    - id: impl-t-037
      status: in-progress
      sprint_id: impl-sprint-8
      epic_id: impl-epic-8
      name: implement-agent-run-and-agent-evidence-audit-model
      deliverable: ledger of agent runs with evidence bindings status transitions and post-run traceability
    - id: impl-t-038
      status: in-progress
      sprint_id: impl-sprint-8
      epic_id: impl-epic-8
      name: verify-write-path-blocking-without-approval
      deliverable: test and demonstration evidence that unsupported or unapproved writes are denied by default
    - id: impl-t-039
      status: in-progress
      sprint_id: impl-sprint-9
      epic_id: impl-epic-9
      name: select-bounded-pilot-application-and-declare-scope-boundaries
      deliverable: approved pilot scope with target environment dependencies constraints and success criteria
    - id: impl-t-040
      status: in-progress
      sprint_id: impl-sprint-9
      epic_id: impl-epic-9
      name: author-research-dossier-for-selected-pilot
      deliverable: versioned research dossier synthesizing real infrastructure facts shared-service contracts constraints and reuse opportunities
    - id: impl-t-041
      status: in-progress
      sprint_id: impl-sprint-9
      epic_id: impl-epic-9
      name: author-application-definition-pack-for-selected-pilot
      deliverable: complete application definition pack including product intent context boundary domain model architecture views and shared-service contracts
    - id: impl-t-042
      status: in-progress
      sprint_id: impl-sprint-9
      epic_id: impl-epic-9
      name: author-verification-specification-and-evidence-map-for-pilot
      deliverable: executable verification specification and evidence map linked to canonical documents registry objects and observed facts
    - id: impl-t-043
      status: in-progress
      sprint_id: impl-sprint-9
      epic_id: impl-epic-9
      name: execute-governed-pilot-flow-through-brokers-and-approvals
      deliverable: auditable run of the pilot using context broker retrieval broker action broker approvals and post-run verification
    - id: impl-t-044
      status: in-progress
      sprint_id: impl-sprint-9
      epic_id: impl-epic-9
      name: compare-first-and-second-pilot-run-for-repeatability
      deliverable: delta report proving or disproving repeatability and exposing hidden manual dependencies
    - id: impl-t-045
      status: in-progress
      sprint_id: impl-sprint-10
      epic_id: impl-epic-10
      name: define-wave-1-kpi-and-slo-catalog
      deliverable: approved KPI and SLO catalog for registry freshness retrieval quality approvals and agent-run governance
    - id: impl-t-046
      status: in-progress
      sprint_id: impl-sprint-10
      epic_id: impl-epic-10
      name: implement-dashboards-and-alerting-for-core-platform-surfaces
      deliverable: dashboards and alerts for discovery health retrieval quality broker actions approval state and audit anomalies
    - id: impl-t-047
      status: in-progress
      sprint_id: impl-sprint-10
      epic_id: impl-epic-10
      name: define-and-implement-retention-rules-for-audit-and-evidence-artifacts
      deliverable: retention policy and technical enforcement for collection outputs evidence packs agent runs and action records
    - id: impl-t-048
      status: in-progress
      sprint_id: impl-sprint-10
      epic_id: impl-epic-10
      name: author-runbooks-for-critical-wave-1-operational-flows
      deliverable: runbooks for ingestion recovery retrieval degradation approval investigation broker denial and audit review scenarios
    - id: impl-t-049
      status: in-progress
      sprint_id: impl-sprint-10
      epic_id: impl-epic-10
      name: conduct-wave-1-readiness-review-with-honest-gap-register
      deliverable: formal readiness review that records residual risks open gaps approved exceptions and decision to proceed or hold
    - id: impl-t-050
      status: in-progress
      sprint_id: impl-sprint-11
      epic_id: impl-epic-10
      name: define-shared-observability-signal-inventory-and-ownership
      deliverable: approved inventory of critical metrics logs audit events and derived health signals with explicit owners source systems and intended operational use
    - id: impl-t-051
      status: in-progress
      sprint_id: impl-sprint-11
      epic_id: impl-epic-10
      name: implement-signal-export-contracts-for-shared-prometheus-and-loki
      deliverable: instrumented registry discovery retrieval approval and agent-run surfaces exposing governed signals consumable by shared prometheus loki and grafana on orchestrator
    - id: impl-t-052
      status: in-progress
      sprint_id: impl-sprint-11
      epic_id: impl-epic-10
      name: version-canonical-health-and-degradation-queries
      deliverable: reviewed query set for freshness ingestion drift retrieval degradation approval backlog and anomalous agent activity used by dashboards and investigations
    - id: impl-t-053
      status: in-progress
      sprint_id: impl-sprint-12
      epic_id: impl-epic-10
      name: publish-shared-grafana-dashboard-pack-for-wave-1-critical-surfaces
      deliverable: shared grafana dashboards covering registry freshness ingestion outcomes retrieval behavior approval queues audit anomalies and agent-run governance
    - id: impl-t-054
      status: in-progress
      sprint_id: impl-sprint-12
      epic_id: impl-epic-10
      name: configure-and-test-alert-routing-escalation-and-contact-points
      deliverable: tested alert routing model with contact points escalation expectations and evidence for critical failure modes across wave-1 surfaces
    - id: impl-t-055
      status: in-progress
      sprint_id: impl-sprint-12
      epic_id: impl-epic-10
      name: operationalize-kpi-slo-and-error-budget-views
      deliverable: decision-grade kpi slo and error budget views used in service review readiness review and go-or-hold governance
    - id: impl-t-056
      status: in-progress
      sprint_id: impl-sprint-13
      epic_id: impl-epic-10
      name: validate-retention-enforcement-on-live-observability-and-audit-surfaces
      deliverable: evidence that retention classes are enforced across collection outputs evidence packs agent runs and applicable shared observability stores
    - id: impl-t-057
      status: in-progress
      sprint_id: impl-sprint-13
      epic_id: impl-epic-10
      name: link-runbooks-from-alerts-dashboards-and-operational-review-surfaces
      deliverable: maintained runbook index with direct linkage from shared dashboards alerts and operational review artifacts for critical scenarios
    - id: impl-t-058
      status: in-progress
      sprint_id: impl-sprint-13
      epic_id: impl-epic-10
      name: execute-observability-drill-for-wave-1-failure-modes
      deliverable: observability drill report covering failed collector drift spike approval expiry or broker anomaly scenarios with findings owners and remediation tracking
```

## Content: Live Audit Synthesis and Exact Wave-1 Registry Contract

Contractul de mai jos nu mai este doar o intentie abstracta derivata din blueprint. El este calibrat pe baza verificarilor read-only executate live cu scripturile existente din repo:

- `subprojects/cluster-full-audit/audit_full.py` pe toate cele 9 noduri `hz.*` din cluster;
- `subprojects/cluster-audit/audit_cluster.py` pe toate cele 9 noduri `hz.*` pentru topologia de retea si vSwitch;
- `subprojects/cluster-ssh-checker/test_cluster_ssh.py` pe inventory-ul aprobat pentru aceasta infrastructura: cele 9 noduri `hz.*`, plus `orchestrator`, `postgres-main` si `imac`;
- `subprojects/runtime-posture-audit/audit_runtime_posture.py` pe `orchestrator`, `postgres-main`, `imac` si toate cele 9 noduri `hz.*`;
- `subprojects/trust-surface-audit/audit_trust_surface.py` pe `orchestrator`, `postgres-main`, `imac` si toate cele 9 noduri `hz.*`, plus probe TLS catre `postgres.neanelu.ro:5432` si `postgres.orchestrator.neanelu.ro:5432`.

Fapte observate care trebuie inghetate in modelul wave-1:

- clusterul auditat operational contine 9 noduri `hz.*`, toate accesibile prin audit read-only;
- inventory-ul operational suplimentar in scope contine `orchestrator`, `postgres-main` si `imac`; din acestea, auditul SSH din 2026-03-08 a confirmat `orchestrator` si `postgres-main` ca reachable, iar `imac` a raspuns cu `connection refused` pe portul 22;
- familiile OS observate in cluster sunt `Ubuntu 24.04.3 LTS`, `Ubuntu 24.04.4 LTS`, `Debian GNU/Linux 13 (trixie)` si `Debian GNU/Linux 11 (bullseye)`;
- hosturile shared observate adauga `orchestrator` pe `Debian GNU/Linux 13 (trixie)` si `postgres-main` pe `Ubuntu 24.04 LTS`;
- topologia Proxmox observata clar prin verificare SSH read-only este formata din 3 instante separate: un cluster Proxmox cu 4 noduri format din `orchestrator`, `hz.215`, `hz.223` si `hz.247`, plus doua instante Proxmox standalone pe `hz.118` si `hz.157`; modelul wave-1 trebuie sa retina atat apartenenta la clusterul `NewCluster`, cat si faptul ca exista hypervisoare standalone in afara lui;
- nodurile Docker observate clar sunt `hz.62`, `hz.113`, `hz.123`, `hz.164` si `orchestrator`;
- nodurile GPU observate clar sunt `hz.62` si `hz.113`;
- segmentele private observate clar includ `10.0.1.0/24`, `10.10.1.0/24`, `10.20.0.0/24` si mai multe retele bridge Docker din gamele `172.17.0.0/16`, `172.18.0.0/16`, `172.19.0.0/16`, `172.20.0.0/16`, `172.30.10.0/24`, `172.30.20.0/24`, `172.30.30.0/24`;
- pe `orchestrator` auditul de runtime a observat Docker activ cu 21 containere, inclusiv `traefik`, `prometheus`, `grafana`, `loki`, `tempo`, `otel-collector`, `openbao`, `zitadel`, `roundcube`, `llm-guard`, `redis-shared` si `watchtower`, ceea ce confirma rolul sau de suprafata shared pentru control plane, observability si servicii comune;
- pe `postgres-main` auditul de runtime a observat runtime PostgreSQL separat pentru aplicatii, bazat pe servicii systemd `postgresql@18-main.service` si `postgres-exporter.service`, plus cron-uri zilnice de `pg_dump`, fara Docker local;
- pe `hz.113` auditul de runtime a observat runtime AI cu containere `vllm-qwen-14b`, `vllm-qwq-32b`, `open-webui`, `openbao-agent-llm` si `nvidia-gpu-exporter`, iar pe `hz.62` a observat `ollama-embed`, `cadvisor`, `node-exporter` si `nvidia-gpu-exporter`;
- pe `hz.123` auditul de runtime a observat stack-ul `flowxify` cu `n8n`, `activepieces`, `postgres:17`, `redis` si gateway/API asociate, iar pe `hz.164` a observat un host Docker dens cu 57 containere si certificate Let's Encrypt active;
- modelul de expunere observat in cluster include simultan `traefik HTTP/HTTPS`, publicari directe de porturi Docker, servicii bind-uite pe loopback si servicii accesibile doar pe reteaua privata; in schimb, probele din 2026-03-08 catre `postgres.neanelu.ro:5432` si `postgres.orchestrator.neanelu.ro:5432` au returnat `connection refused`, deci expunerea publica TCP/SNI pe `5432` trebuie tratata ca stare de reconciliat si validat, nu ca acces extern deja functional.
- aceleasi hosturi poarta simultan roluri multiple observate: `orchestrator` este membru Proxmox, host shared-service si host de observabilitate, `hz.113` este atat host GPU cat si runtime aplicativ/AI, iar `postgres-main` este atat host de baza de date cat si tinta monitorizata; modelul wave-1 trebuie deci sa pastreze rol primar plus asignari de rol observate many-to-many;
- sursele reale care au corectat acest plan includ explicit `runtime-posture-audit` si `trust-surface-audit`, iar contractul taxonomic trebuie sa le poata reprezenta fara extensii ad-hoc.

Din aceste fapte rezulta ca taxonomia si schema DB wave-1 trebuie sa fie suficient de stricte pentru integritate relationala, dar suficient de bogate pentru a acoperi simultan: hosturi fizice, hypervisoare, servicii shared, containere, expuneri externe, retele private, dovezi observate si binding-ul la documentele canonice.

## Content: Exact Wave-1 Taxonomy Structure

Taxonomiile wave-1 trebuie implementate in PostgreSQL ca vocabulary controlat versionat, nu ca string-uri libere dispersate in tabelele de business. Domeniile minime obligatorii sunt urmatoarele.

### 1. Taxonomy Domain `entity_kind`

Valori obligatorii wave-1:

- `cluster`
- `proxmox_cluster`
- `host`
- `host_role_assignment`
- `cluster_membership`
- `host_hardware_snapshot`
- `gpu_device`
- `shared_service`
- `service_instance`
- `service_exposure`
- `service_dependency`
- `network_segment`
- `network_interface`
- `ip_address_assignment`
- `route_entry`
- `dns_resolver_state`
- `storage_asset`
- `ownership_assignment`
- `document`
- `document_version`
- `document_entity_binding`
- `document_chunk`
- `chunk_embedding`
- `evidence_pack`
- `evidence_pack_item`
- `discovery_source`
- `collection_run`
- `observed_fact`
- `evidence_artifact`
- `reconciliation_result`
- `prompt_template_registry`
- `agent_run`
- `agent_evidence`
- `action_request`
- `policy_record`
- `approval_record`
- `change_log`

Regula de normalizare pentru `entity_kind`:

- lista `entity_kind` trebuie sa acopere toate tabelele relationale care pot fi tinta pentru ownership, approval, document binding, evidence binding, reconciliation sau change logging; aliasurile conceptuale din blueprint care nu au tabel dedicat in wave-1 se modeleaza prin combinatia dintre entitatea relationala existenta si taxonomia asociata, nu prin termeni fara suport in schema.

### 2. Taxonomy Domain `host_role`

Valori obligatorii wave-1:

- `physical_cluster_node`
- `proxmox_hypervisor`
- `proxmox_cluster_member`
- `standalone_proxmox_host`
- `gpu_inference_node`
- `application_runtime_host`
- `shared_service_host`
- `edge_gateway_host`
- `database_host`
- `monitored_host`
- `observability_host`
- `mail_collaboration_host`
- `automation_host`
- `development_runtime_host`

### 3. Taxonomy Domain `environment`

Valori obligatorii wave-1:

- `production`
- `shared-platform`
- `development`
- `staging`
- `bootstrap`

### 4. Taxonomy Domain `service_kind`

Valori obligatorii wave-1, derivate din blueprint si din auditul live:

- `postgresql`
- `pgbouncer`
- `redis`
- `traefik`
- `openbao`
- `zitadel`
- `grafana`
- `prometheus`
- `loki`
- `tempo`
- `otel_collector`
- `cadvisor`
- `node_exporter`
- `pve_exporter`
- `postgres_exporter`
- `oauth2_proxy`
- `vllm`
- `ollama`
- `open_webui`
- `n8n`
- `activepieces`
- `cloudbeaver`
- `watchtower`
- `kafka`
- `neo4j`
- `temporal`
- `roundcube`
- `stalwart`
- `llm_guard`
- `mail_gateway`
- `api_gateway`
- `application_api`
- `application_worker`
- `web_frontend`
- `job_scheduler`

Regula de mapare obligatorie pentru `service_kind`:

- vocabularul retine produsul sau clasa canonica a serviciului, iar identificatori runtime-specifici precum `redis-shared`, numele containerului sau numele Compose raman in `instance_name`, `container_name` si `compose_project_name`, nu inlocuiesc taxonomia controlata.

### 5. Taxonomy Domain `runtime_kind`

Valori obligatorii wave-1:

- `systemd_service`
- `docker_container`
- `docker_compose_stack`
- `bare_metal_host`
- `proxmox_host`
- `lxc_guest`
- `virtual_machine`

### 6. Taxonomy Domain `network_segment_kind`

Valori obligatorii wave-1:

- `public_underlay`
- `private_vswitch`
- `docker_bridge`
- `docker_overlay`
- `loopback`
- `service_bind_network`
- `management_network`

### 7. Taxonomy Domain `address_scope`

Valori obligatorii wave-1:

- `public_ipv4`
- `public_ipv6`
- `private_ipv4`
- `loopback`
- `link_local`
- `bridge_local`

### 8. Taxonomy Domain `exposure_method`

Valori obligatorii wave-1:

- `traefik_http`
- `traefik_https`
- `traefik_tcp_sni`
- `direct_host_port`
- `loopback_only`
- `private_vlan_only`
- `internal_docker_network`
- `not_exposed`

### 9. Taxonomy Domain `storage_kind`

Valori obligatorii wave-1:

- `local_disk`
- `mdraid`
- `nvme`
- `network_storage`
- `docker_volume`
- `bind_mount`
- `backup_target`

### 10. Taxonomy Domain `document_kind`

Valori obligatorii wave-1, conform blueprint-ului:

- `adr`
- `cluster_overview`
- `node_record`
- `hypervisor_record`
- `vm_lxc_record`
- `network_segment_record`
- `storage_record`
- `backup_restore_record`
- `external_access_record`
- `shared_service_dossier`
- `service_consumption_contract`
- `service_contract_pack`
- `runbook`
- `observability_onboarding_record`
- `incident_recovery_runbook`
- `security_control_record`
- `deployment_policy_record`
- `policy_pack`
- `change_template`
- `approval_pattern`
- `ownership_matrix`
- `product_intent_record`
- `context_boundary_record`
- `canonical_domain_model`
- `architecture_view_pack`
- `service_contracts`
- `application_definition_pack`
- `engineering_policy_pack`
- `repository_instruction_layer`
- `research_dossier`
- `verification_specification`
- `evidence_map`
- `task_brief_template`
- `agent_policy`
- `retrieval_policy`
- `forbidden_assumptions_policy`
- `action_authorization_policy`
- `evidence_requirements`
- `prompt_template_registry`
- `operational_declaration`
- `data_governance_compliance_declaration`

### 11. Taxonomy Domain `os_family`

Valori obligatorii wave-1:

- `ubuntu`
- `debian`
- `macos`
- `unknown`

### 12. Taxonomy Domain `lifecycle_status`

Valori obligatorii wave-1:

- `planned`
- `active`
- `degraded`
- `inactive`
- `retired`
- `unknown`

### 13. Taxonomy Domain `observation_status`

Valori obligatorii wave-1:

- `observed`
- `partially_observed`
- `unreachable`
- `error`
- `stale`

### 14. Taxonomy Domain `discovery_source_kind`

Valori obligatorii wave-1:

- `ssh_full_audit`
- `ssh_network_audit`
- `ssh_connectivity_check`
- `runtime_posture_audit`
- `trust_surface_audit`
- `docker_runtime_inspection`
- `systemd_runtime_inspection`
- `tls_endpoint_probe`
- `sshd_config_inspection`
- `secrets_surface_inspection`
- `traefik_config_inspection`
- `compose_manifest_inspection`
- `canonical_document_parse`
- `manual_binding`

### 15. Taxonomy Domain `evidence_kind`

Valori obligatorii wave-1:

- `command_stdout`
- `parsed_config_file`
- `structured_json_export`
- `document_version_binding`
- `route_definition`
- `interface_snapshot`
- `container_runtime_snapshot`
- `security_setting_snapshot`
- `runtime_posture_snapshot`
- `trust_surface_snapshot`
- `tls_probe_result`
- `sshd_config_snapshot`
- `secret_material_finding`

### 16. Taxonomy Domain `membership_role`

Valori obligatorii wave-1:

- `operational_cluster_member`
- `proxmox_quorum_member`
- `proxmox_non_quorate_member`
- `standalone_hypervisor_anchor`
- `external_scoped_asset`

### 17. Taxonomy Domain `interface_kind`

Valori obligatorii wave-1:

- `physical_nic`
- `bond`
- `linux_bridge`
- `ovs_bridge`
- `docker_bridge`
- `veth`
- `vlan_subinterface`
- `loopback_interface`
- `tunnel_interface`

### 18. Taxonomy Domain `owner_type`

Valori obligatorii wave-1:

- `named_individual`
- `team`
- `role_group`
- `service_account`
- `external_vendor`
- `automated_control_plane`

### 19. Taxonomy Domain `collection_run_status`

Valori obligatorii wave-1:

- `queued`
- `running`
- `succeeded`
- `partial_success`
- `failed`
- `cancelled`
- `timed_out`

### 20. Taxonomy Domain `reconciliation_result_status`

Valori obligatorii wave-1:

- `matched`
- `drift_detected`
- `missing_canonical`
- `missing_observed`
- `requires_review`
- `approved_override`
- `suppressed`

### 21. Taxonomy Domain `exposure_health`

Valori obligatorii wave-1:

- `healthy`
- `degraded`
- `connection_refused`
- `timeout`
- `dns_error`
- `tls_handshake_failed`
- `design_only`
- `unknown`

### 22. Taxonomy Domain `relationship_kind`

Valori obligatorii wave-1:

- `contains`
- `hosts`
- `member_of`
- `runs_on`
- `depends_on`
- `exposes`
- `uses_network`
- `uses_storage`
- `owned_by`
- `documented_by`
- `observed_by`
- `backed_up_by`
- `protected_by`

## Content: Exact Wave-1 Database Schema, Tables and Columns

Schema wave-1 trebuie organizata pe schemate functionale clare. Denumirile de mai jos sunt contractul de referinta pentru migrarea initiala.

### Schema `taxonomy`

#### Table `taxonomy_domain`

Coloane obligatorii:

- `taxonomy_domain_id` UUID PK
- `domain_code` TEXT UNIQUE
- `name` TEXT
- `description` TEXT
- `schema_version` TEXT
- `is_active` BOOLEAN
- `created_at` TIMESTAMPTZ
- `updated_at` TIMESTAMPTZ

#### Table `taxonomy_term`

Coloane obligatorii:

- `taxonomy_term_id` UUID PK
- `taxonomy_domain_id` UUID FK -> `taxonomy_domain`
- `term_code` TEXT
- `display_name` TEXT
- `description` TEXT
- `parent_term_id` UUID NULL FK -> `taxonomy_term`
- `sort_order` INTEGER
- `is_active` BOOLEAN
- `metadata_jsonb` JSONB
- `created_at` TIMESTAMPTZ
- `updated_at` TIMESTAMPTZ

### Schema `registry`

#### Table `cluster`

Coloane obligatorii:

- `cluster_id` UUID PK
- `cluster_code` TEXT UNIQUE
- `name` TEXT
- `entity_kind_term_id` UUID FK -> `taxonomy_term`
- `environment_term_id` UUID FK -> `taxonomy_term`
- `lifecycle_term_id` UUID FK -> `taxonomy_term`
- `description` TEXT
- `canonical_document_id` UUID NULL
- `metadata_jsonb` JSONB
- `created_at` TIMESTAMPTZ
- `updated_at` TIMESTAMPTZ

#### Table `host`

Coloane obligatorii:

- `host_id` UUID PK
- `cluster_id` UUID NULL FK -> `cluster` (`primary operational cluster when applicable`)
- `host_code` TEXT UNIQUE
- `hostname` TEXT
- `ssh_alias` TEXT NULL
- `fqdn` TEXT NULL
- `entity_kind_term_id` UUID FK -> `taxonomy_term`
- `primary_host_role_term_id` UUID NULL FK -> `taxonomy_term` (`host_role` domain)
- `environment_term_id` UUID FK -> `taxonomy_term`
- `lifecycle_term_id` UUID FK -> `taxonomy_term`
- `os_family_term_id` UUID NULL FK -> `taxonomy_term` (`os_family` domain)
- `os_version_text` TEXT
- `kernel_version_text` TEXT
- `architecture_text` TEXT
- `is_gpu_capable` BOOLEAN
- `is_docker_host` BOOLEAN
- `is_hypervisor` BOOLEAN
- `primary_public_ipv4` INET NULL
- `primary_private_ipv4` INET NULL
- `observed_hostname` TEXT
- `confidence_score` NUMERIC(5,4)
- `metadata_jsonb` JSONB
- `created_at` TIMESTAMPTZ
- `updated_at` TIMESTAMPTZ

#### Table `host_role_assignment`

Coloane obligatorii:

- `host_role_assignment_id` UUID PK
- `host_id` UUID FK -> `host`
- `host_role_term_id` UUID FK -> `taxonomy_term` (`host_role` domain)
- `is_primary` BOOLEAN
- `assignment_source_text` TEXT NULL
- `collection_run_id` UUID NULL FK -> `discovery.collection_run`
- `observed_at` TIMESTAMPTZ NULL
- `created_at` TIMESTAMPTZ
- `updated_at` TIMESTAMPTZ

#### Table `cluster_membership`

Coloane obligatorii:

- `cluster_membership_id` UUID PK
- `cluster_id` UUID FK -> `cluster`
- `host_id` UUID FK -> `host`
- `membership_role_term_id` UUID FK -> `taxonomy_term` (`membership_role` domain)
- `member_node_name_text` TEXT NULL
- `member_node_id_text` TEXT NULL
- `membership_source_text` TEXT NULL
- `is_quorate_member` BOOLEAN NULL
- `collection_run_id` UUID NULL FK -> `discovery.collection_run`
- `observed_at` TIMESTAMPTZ NULL
- `created_at` TIMESTAMPTZ
- `updated_at` TIMESTAMPTZ

#### Table `host_hardware_snapshot`

Coloane obligatorii:

- `host_hardware_snapshot_id` UUID PK
- `host_id` UUID FK -> `host`
- `collection_run_id` UUID FK -> `discovery.collection_run`
- `cpu_model` TEXT
- `cpu_socket_count` INTEGER
- `cpu_core_count` INTEGER
- `ram_total_bytes` BIGINT
- `ram_used_bytes` BIGINT
- `ram_free_bytes` BIGINT
- `swap_total_bytes` BIGINT
- `swap_used_bytes` BIGINT
- `gpu_count` INTEGER
- `hardware_jsonb` JSONB
- `observed_at` TIMESTAMPTZ

#### Table `gpu_device`

Coloane obligatorii:

- `gpu_device_id` UUID PK
- `host_id` UUID FK -> `host`
- `gpu_index` INTEGER
- `vendor_name` TEXT
- `model_name` TEXT
- `uuid_text` TEXT
- `driver_version_text` TEXT
- `memory_total_mb` INTEGER
- `memory_used_mb` INTEGER
- `memory_free_mb` INTEGER
- `utilization_gpu_pct` NUMERIC(5,2)
- `utilization_memory_pct` NUMERIC(5,2)
- `temperature_celsius` NUMERIC(5,2)
- `power_draw_watts` NUMERIC(8,2)
- `power_limit_watts` NUMERIC(8,2)
- `fan_pct` NUMERIC(5,2)
- `compute_capability` TEXT
- `collection_run_id` UUID FK -> `discovery.collection_run`
- `observed_at` TIMESTAMPTZ

#### Table `network_segment`

Coloane obligatorii:

- `network_segment_id` UUID PK
- `segment_code` TEXT UNIQUE
- `name` TEXT
- `segment_kind_term_id` UUID FK -> `taxonomy_term`
- `environment_term_id` UUID FK -> `taxonomy_term`
- `cidr` CIDR
- `vlan_id_text` TEXT NULL
- `mtu` INTEGER NULL
- `description` TEXT
- `source_of_truth` TEXT
- `created_at` TIMESTAMPTZ
- `updated_at` TIMESTAMPTZ

#### Table `network_interface`

Coloane obligatorii:

- `network_interface_id` UUID PK
- `host_id` UUID FK -> `host`
- `network_segment_id` UUID NULL FK -> `network_segment`
- `interface_name` TEXT
- `parent_interface_name` TEXT NULL
- `interface_kind_term_id` UUID NULL FK -> `taxonomy_term` (`interface_kind` domain)
- `state_text` TEXT
- `mac_address` MACADDR NULL
- `mtu` INTEGER NULL
- `is_virtual` BOOLEAN
- `metadata_jsonb` JSONB
- `created_at` TIMESTAMPTZ
- `updated_at` TIMESTAMPTZ

#### Table `ip_address_assignment`

Coloane obligatorii:

- `ip_address_assignment_id` UUID PK
- `network_interface_id` UUID FK -> `network_interface`
- `network_segment_id` UUID NULL FK -> `network_segment`
- `address` INET
- `prefix_length` INTEGER
- `address_scope_term_id` UUID FK -> `taxonomy_term`
- `is_primary` BOOLEAN
- `is_public` BOOLEAN
- `observed_at` TIMESTAMPTZ
- `collection_run_id` UUID FK -> `discovery.collection_run`

#### Table `route_entry`

Coloane obligatorii:

- `route_entry_id` UUID PK
- `host_id` UUID FK -> `host`
- `network_segment_id` UUID NULL FK -> `network_segment`
- `destination_cidr` CIDR
- `gateway_ip` INET NULL
- `device_name` TEXT NULL
- `route_type_text` TEXT NULL
- `is_default_route` BOOLEAN
- `raw_route_text` TEXT
- `collection_run_id` UUID FK -> `discovery.collection_run`
- `observed_at` TIMESTAMPTZ

#### Table `dns_resolver_state`

Coloane obligatorii:

- `dns_resolver_state_id` UUID PK
- `host_id` UUID FK -> `host`
- `resolver_list_text` TEXT
- `resolver_jsonb` JSONB
- `collection_run_id` UUID FK -> `discovery.collection_run`
- `observed_at` TIMESTAMPTZ

#### Table `storage_asset`

Coloane obligatorii:

- `storage_asset_id` UUID PK
- `host_id` UUID FK -> `host`
- `storage_kind_term_id` UUID FK -> `taxonomy_term`
- `device_name` TEXT
- `model_text` TEXT NULL
- `size_bytes` BIGINT NULL
- `is_rotational` BOOLEAN NULL
- `filesystem_type_text` TEXT NULL
- `mountpoint_text` TEXT NULL
- `backing_device_text` TEXT NULL
- `metadata_jsonb` JSONB
- `collection_run_id` UUID FK -> `discovery.collection_run`
- `observed_at` TIMESTAMPTZ

#### Table `shared_service`

Coloane obligatorii:

- `shared_service_id` UUID PK
- `service_code` TEXT UNIQUE
- `name` TEXT
- `service_kind_term_id` UUID FK -> `taxonomy_term`
- `environment_term_id` UUID FK -> `taxonomy_term`
- `lifecycle_term_id` UUID FK -> `taxonomy_term`
- `description` TEXT
- `canonical_document_id` UUID NULL
- `metadata_jsonb` JSONB
- `created_at` TIMESTAMPTZ
- `updated_at` TIMESTAMPTZ

#### Table `service_instance`

Coloane obligatorii:

- `service_instance_id` UUID PK
- `shared_service_id` UUID FK -> `shared_service`
- `host_id` UUID NULL FK -> `host`
- `runtime_kind_term_id` UUID FK -> `taxonomy_term`
- `instance_name` TEXT
- `container_name` TEXT NULL
- `systemd_unit_name` TEXT NULL
- `compose_project_name` TEXT NULL
- `image_reference` TEXT NULL
- `version_text` TEXT NULL
- `status_text` TEXT
- `is_primary` BOOLEAN
- `metadata_jsonb` JSONB
- `collection_run_id` UUID NULL FK -> `discovery.collection_run`
- `observed_at` TIMESTAMPTZ NULL

#### Table `service_exposure`

Coloane obligatorii:

- `service_exposure_id` UUID PK
- `service_instance_id` UUID FK -> `service_instance`
- `exposure_method_term_id` UUID FK -> `taxonomy_term`
- `design_source_document_id` UUID NULL FK -> `docs.document`
- `hostname` TEXT NULL
- `host_ip` INET NULL
- `listen_port` INTEGER
- `backend_host` TEXT NULL
- `backend_port` INTEGER NULL
- `protocol_text` TEXT
- `sni_hostname` TEXT NULL
- `path_prefix` TEXT NULL
- `is_external` BOOLEAN
- `is_declared_in_design` BOOLEAN
- `is_tls_terminated` BOOLEAN
- `is_live_probe_success` BOOLEAN NULL
- `observed_health_term_id` UUID NULL FK -> `taxonomy_term` (`exposure_health` domain)
- `probe_confidence_score` NUMERIC(5,4) NULL
- `last_probe_result_text` TEXT NULL
- `last_probe_checked_at` TIMESTAMPTZ NULL
- `metadata_jsonb` JSONB
- `collection_run_id` UUID NULL FK -> `discovery.collection_run`
- `observed_at` TIMESTAMPTZ NULL

#### Table `service_dependency`

Coloane obligatorii:

- `service_dependency_id` UUID PK
- `source_service_instance_id` UUID FK -> `service_instance`
- `target_service_instance_id` UUID NULL FK -> `service_instance`
- `target_shared_service_id` UUID NULL FK -> `shared_service`
- `relationship_kind_term_id` UUID FK -> `taxonomy_term`
- `dependency_role_text` TEXT
- `is_hard_dependency` BOOLEAN
- `evidence_confidence` NUMERIC(5,4)
- `collection_run_id` UUID NULL FK -> `discovery.collection_run`
- `observed_at` TIMESTAMPTZ NULL

#### Table `ownership_assignment`

Coloane obligatorii:

- `ownership_assignment_id` UUID PK
- `entity_kind_term_id` UUID FK -> `taxonomy_term`
- `entity_id` UUID
- `owner_type_term_id` UUID FK -> `taxonomy_term` (`owner_type` domain)
- `owner_code` TEXT
- `responsibility_text` TEXT
- `is_primary` BOOLEAN
- `valid_from` TIMESTAMPTZ
- `valid_to` TIMESTAMPTZ NULL

### Schema `docs`

#### Table `document`

Coloane obligatorii:

- `document_id` UUID PK
- `document_kind_term_id` UUID FK -> `taxonomy_term`
- `document_path` TEXT UNIQUE
- `title` TEXT
- `status_text` TEXT
- `owner_code` TEXT NULL
- `source_repo_url` TEXT
- `source_branch` TEXT NULL
- `current_version_id` UUID NULL
- `created_at` TIMESTAMPTZ
- `updated_at` TIMESTAMPTZ

#### Table `document_version`

Coloane obligatorii:

- `document_version_id` UUID PK
- `document_id` UUID FK -> `document`
- `git_commit_sha` TEXT
- `content_hash` TEXT
- `frontmatter_jsonb` JSONB
- `body_excerpt_text` TEXT
- `is_current` BOOLEAN
- `created_at` TIMESTAMPTZ

#### Table `document_entity_binding`

Coloane obligatorii:

- `document_entity_binding_id` UUID PK
- `document_version_id` UUID FK -> `document_version`
- `entity_kind_term_id` UUID FK -> `taxonomy_term`
- `entity_id` UUID
- `binding_role_text` TEXT
- `confidence_score` NUMERIC(5,4)
- `created_at` TIMESTAMPTZ

### Schema `retrieval`

#### Table `document_chunk`

Coloane obligatorii:

- `document_chunk_id` UUID PK
- `document_version_id` UUID FK -> `docs.document_version`
- `chunk_index` INTEGER
- `chunk_hash` TEXT
- `content_text` TEXT
- `token_count` INTEGER
- `section_path_text` TEXT NULL
- `metadata_jsonb` JSONB
- `created_at` TIMESTAMPTZ

#### Table `chunk_embedding`

Coloane obligatorii:

- `chunk_embedding_id` UUID PK
- `document_chunk_id` UUID FK -> `document_chunk`
- `embedding_model_code` TEXT
- `embedding_vector` VECTOR
- `lexical_tsv` TSVECTOR NULL
- `summary_text` TEXT NULL
- `metadata_jsonb` JSONB
- `created_at` TIMESTAMPTZ

#### Table `evidence_pack`

Coloane obligatorii:

- `evidence_pack_id` UUID PK
- `pack_code` TEXT UNIQUE
- `task_type_code` TEXT
- `request_scope_jsonb` JSONB
- `selection_rationale_text` TEXT
- `token_budget` INTEGER NULL
- `created_by` TEXT
- `created_at` TIMESTAMPTZ

#### Table `evidence_pack_item`

Coloane obligatorii:

- `evidence_pack_item_id` UUID PK
- `evidence_pack_id` UUID FK -> `evidence_pack`
- `item_order` INTEGER
- `entity_kind_term_id` UUID FK -> `taxonomy_term`
- `entity_id` UUID NULL
- `document_chunk_id` UUID NULL FK -> `document_chunk`
- `evidence_artifact_id` UUID NULL FK -> `discovery.evidence_artifact`
- `inclusion_reason_text` TEXT
- `is_mandatory` BOOLEAN
- `created_at` TIMESTAMPTZ

### Schema `discovery`

#### Table `discovery_source`

Coloane obligatorii:

- `discovery_source_id` UUID PK
- `source_kind_term_id` UUID FK -> `taxonomy_term`
- `source_code` TEXT UNIQUE
- `name` TEXT
- `tool_path` TEXT NULL
- `command_template` TEXT NULL
- `is_read_only` BOOLEAN
- `description` TEXT
- `created_at` TIMESTAMPTZ

#### Table `collection_run`

Coloane obligatorii:

- `collection_run_id` UUID PK
- `discovery_source_id` UUID FK -> `discovery_source`
- `run_code` TEXT UNIQUE
- `target_scope_jsonb` JSONB
- `started_at` TIMESTAMPTZ
- `finished_at` TIMESTAMPTZ NULL
- `status_term_id` UUID FK -> `taxonomy_term` (`collection_run_status` domain)
- `executor_identity` TEXT
- `raw_output_path` TEXT NULL
- `summary_jsonb` JSONB

#### Table `observed_fact`

Coloane obligatorii:

- `observed_fact_id` UUID PK
- `collection_run_id` UUID FK -> `collection_run`
- `entity_kind_term_id` UUID FK -> `taxonomy_term`
- `entity_id` UUID
- `fact_namespace` TEXT
- `fact_key` TEXT
- `fact_value_jsonb` JSONB
- `observation_status_term_id` UUID FK -> `taxonomy_term`
- `confidence_score` NUMERIC(5,4)
- `observed_at` TIMESTAMPTZ

#### Table `evidence_artifact`

Coloane obligatorii:

- `evidence_artifact_id` UUID PK
- `collection_run_id` UUID FK -> `collection_run`
- `evidence_kind_term_id` UUID FK -> `taxonomy_term`
- `artifact_path` TEXT NULL
- `artifact_hash` TEXT NULL
- `mime_type` TEXT NULL
- `content_excerpt_text` TEXT NULL
- `metadata_jsonb` JSONB
- `created_at` TIMESTAMPTZ

#### Table `reconciliation_result`

Coloane obligatorii:

- `reconciliation_result_id` UUID PK
- `entity_kind_term_id` UUID FK -> `taxonomy_term`
- `entity_id` UUID
- `canonical_document_version_id` UUID NULL FK -> `docs.document_version`
- `collection_run_id` UUID FK -> `collection_run`
- `result_status_term_id` UUID FK -> `taxonomy_term` (`reconciliation_result_status` domain)
- `drift_category_text` TEXT
- `canonical_value_jsonb` JSONB
- `observed_value_jsonb` JSONB
- `diff_jsonb` JSONB
- `requires_approval` BOOLEAN
- `created_at` TIMESTAMPTZ

### Schema `agent_control`

#### Table `prompt_template_registry`

Coloane obligatorii:

- `prompt_template_registry_id` UUID PK
- `template_code` TEXT UNIQUE
- `task_type_code` TEXT
- `template_version` TEXT
- `template_text` TEXT
- `policy_record_id` UUID NULL FK -> `governance.policy_record`
- `document_version_id` UUID NULL FK -> `docs.document_version`
- `is_active` BOOLEAN
- `created_at` TIMESTAMPTZ
- `updated_at` TIMESTAMPTZ

#### Table `agent_run`

Coloane obligatorii:

- `agent_run_id` UUID PK
- `run_code` TEXT UNIQUE
- `agent_identity` TEXT
- `task_type_code` TEXT
- `prompt_template_registry_id` UUID NULL FK -> `prompt_template_registry`
- `approval_record_id` UUID NULL FK -> `governance.approval_record`
- `evidence_pack_id` UUID NULL FK -> `retrieval.evidence_pack`
- `requested_scope_jsonb` JSONB
- `status_text` TEXT
- `started_at` TIMESTAMPTZ
- `finished_at` TIMESTAMPTZ NULL
- `created_at` TIMESTAMPTZ

#### Table `agent_evidence`

Coloane obligatorii:

- `agent_evidence_id` UUID PK
- `agent_run_id` UUID FK -> `agent_run`
- `entity_kind_term_id` UUID FK -> `taxonomy_term`
- `entity_id` UUID NULL
- `document_chunk_id` UUID NULL FK -> `retrieval.document_chunk`
- `evidence_artifact_id` UUID NULL FK -> `discovery.evidence_artifact`
- `evidence_role_text` TEXT
- `confidence_score` NUMERIC(5,4)
- `created_at` TIMESTAMPTZ

#### Table `action_request`

Coloane obligatorii:

- `action_request_id` UUID PK
- `request_code` TEXT UNIQUE
- `agent_run_id` UUID NULL FK -> `agent_run`
- `approval_record_id` UUID NULL FK -> `governance.approval_record`
- `action_class_text` TEXT
- `target_scope_jsonb` JSONB
- `requested_change_jsonb` JSONB
- `status_text` TEXT
- `executed_at` TIMESTAMPTZ NULL
- `created_at` TIMESTAMPTZ

### Schema `governance`

#### Table `policy_record`

Coloane obligatorii:

- `policy_record_id` UUID PK
- `policy_code` TEXT UNIQUE
- `name` TEXT
- `scope_text` TEXT
- `document_version_id` UUID NULL FK -> `docs.document_version`
- `is_active` BOOLEAN
- `created_at` TIMESTAMPTZ
- `updated_at` TIMESTAMPTZ

#### Table `approval_record`

Coloane obligatorii:

- `approval_record_id` UUID PK
- `approval_code` TEXT UNIQUE
- `entity_kind_term_id` UUID FK -> `taxonomy_term`
- `entity_id` UUID
- `change_scope_jsonb` JSONB
- `requested_by` TEXT
- `approved_by` TEXT NULL
- `status_text` TEXT
- `expires_at` TIMESTAMPTZ NULL
- `created_at` TIMESTAMPTZ
- `updated_at` TIMESTAMPTZ

#### Table `change_log`

Coloane obligatorii:

- `change_log_id` UUID PK
- `change_code` TEXT UNIQUE
- `entity_kind_term_id` UUID FK -> `taxonomy_term`
- `entity_id` UUID
- `change_source_text` TEXT
- `change_summary_text` TEXT
- `action_request_id` UUID NULL FK -> `agent_control.action_request`
- `approval_record_id` UUID NULL FK -> `approval_record`
- `collection_run_id` UUID NULL FK -> `discovery.collection_run`
- `reconciliation_result_id` UUID NULL FK -> `discovery.reconciliation_result`
- `canonical_document_version_id` UUID NULL FK -> `docs.document_version`
- `before_state_jsonb` JSONB NULL
- `after_state_jsonb` JSONB NULL
- `rollback_reference_text` TEXT NULL
- `changed_by` TEXT
- `changed_at` TIMESTAMPTZ
- `created_at` TIMESTAMPTZ

## Content: Modeling Rules for Columns and Constraints

Regulile obligatorii pentru coloanele wave-1 sunt urmatoarele:

- IP-urile se stocheaza in `INET`, subretelele in `CIDR`, nu in `TEXT` liber;
- metadata variabila merge in `JSONB`, dar doar dupa ce a fost extras tot ce este stabil si interogabil in coloane relationale dedicate;
- toate tabelele de business au `created_at`, `updated_at`, iar tabelele observate au suplimentar `observed_at` sau `started_at`/`finished_at`;
- toate tabelele care reprezinta fapte observate trebuie sa poarte `collection_run_id`;
- nomenclatura blueprint trebuie normalizata strict la schema wave-1 astfel: `nodes`, `hypervisors`, `virtual_machines` si `lxcs` se reprezinta prin `registry.host` plus roluri si membership-uri, `networks` prin `registry.network_segment` + `registry.network_interface` + `registry.ip_address_assignment` + `registry.route_entry`, `storage_units` prin `registry.storage_asset`, `observations` prin `discovery.observed_fact`, `runbooks` prin `docs.document` cu `document_kind` specializat, `agent_policies` prin `governance.policy_record`, iar `approvals` prin `governance.approval_record`;
- `registry.cluster` trebuie sa poata modela atat clusterul operational principal al infrastructurii, cat si sub-clustere de virtualizare precum un `proxmox_cluster`, iar distinctia se face explicit prin `entity_kind_term_id`, nu prin conventii de nume;
- `registry.host.cluster_id` este optional si retine doar ancora operationala primara a hostului atunci cand aceasta exista justificat; asset-urile in scope dar externe sau paralele, precum `postgres-main` sau `imac`, pot ramane fara ancora de cluster pana la aparitia unei relatii operationale demonstrate, iar apartenentele secundare sau paralele, inclusiv membership-ul intr-un cluster Proxmox, se modeleaza exclusiv prin `registry.cluster_membership`;
- `registry.host` retine cel mult un `primary_host_role_term_id` de convenience, dar adevarul complet despre roluri trebuie pastrat in `registry.host_role_assignment`, astfel incat un host sa poata avea simultan roluri precum `proxmox_cluster_member`, `shared_service_host`, `observability_host`, `gpu_inference_node` sau `monitored_host` fara pierdere de semantica;
- cardinalitatea minima obligatorie pentru hosturi este: zero sau un `cluster_id` operational primar, unul sau mai multe roluri observate in `host_role_assignment`, si zero sau mai multe apartenente explicite in `cluster_membership`; daca exista roluri multiple, exact unul poate fi marcat `is_primary=true` in `host_role_assignment`;
- un host etichetat `standalone_proxmox_host` nu trebuie legat la un `proxmox_cluster` prin `registry.cluster_membership` decat daca auditul observa explicit `corosync` si configuratie de cluster partajata;
- `registry.cluster_membership` este relatia canonica many-to-many dintre `host` si `cluster`; o combinatie `host_id + cluster_id + membership_role_term_id` nu trebuie duplicata pentru aceeasi fereastra de valabilitate observata;
- `registry.service_instance.service_kind_term_id` trebuie sa foloseasca un vocabular canonic suficient de bogat pentru servicii observate real, iar denumirile concrete de container, compose project sau unitate systemd raman campuri runtime, nu substitut pentru taxonomie;
- cardinalitatea minima obligatorie pentru servicii este: un `shared_service` poate avea una sau mai multe `service_instance`, iar o `service_instance` poate avea zero sau mai multe `service_exposure`; `service_dependency` trebuie sa refere exact o tinta logica, adica fie `target_service_instance_id`, fie `target_shared_service_id`, dar nu ambele simultan si nu niciuna;
- `registry.service_exposure` trebuie sa separe explicit intentia de design de starea observata live prin `is_declared_in_design`, `is_live_probe_success`, `observed_health_term_id`, rezultate de proba si legatura la documentul sursa, astfel incat o ruta definita dar nefunctionala sa nu fie confundata cu una validata operational;
- toate entitatile care vor fi folosite de retrieval, reconciliere sau control plane trebuie sa aiba `lifecycle`, `confidence`, `owner` si binding la documente sau la evidenta;
- `retrieval.document_chunk` si `retrieval.chunk_embedding` trebuie sa fie strict version-bound la `docs.document_version`, astfel incat niciun chunk semantic sa nu pluteasca fara sursa canonica exacta si fara hash adresabil;
- cardinalitatea minima obligatorie pentru documente este: un `document` poate avea mai multe `document_version`, exact una poate fi `is_current=true`, iar `document_entity_binding` trebuie sa lege o versiune concreta de document de exact o entitate canonica tinta;
- `agent_control.agent_run`, `agent_control.agent_evidence` si `agent_control.action_request` trebuie sa poarte binding la approval, evidence pack si surse de evidenta, astfel incat orice actiune sa poata fi reconstruita auditabil cap-coada;
- cardinalitatea minima obligatorie pentru ownership si guvernanta este: o entitate poate avea mai multe `ownership_assignment`, dar cel mult una activa cu `is_primary=true` pentru acelasi tip de responsabilitate; `approval_record` si `change_log` trebuie sa refere exact o entitate tinta prin perechea `entity_kind_term_id + entity_id`;
- `governance.change_log` este obligatoriu pentru orice mutatie materiala aprobata, reconciliata, rollback-uita sau executata in afara unei rulari agentice, tocmai pentru a acoperi schimbari manuale, importuri controlate si remediere operationala care nu trebuie sa dispara din audit trail;
- `research_dossier`, `application_definition_pack`, `verification_specification` si `evidence_map` trebuie modelate ca artefacte canonice obligatorii pentru orice aplicatie noua guvernata de platforma, nu ca documente optionale lasate la discretia echipei;
- identificatorii de host trebuie separati strict: `host_code` si `ssh_alias` sunt identificatori operationali interni, `hostname` este numele observat pe host, iar `fqdn` sau hostname-ul de expunere extern trebuie populate doar din evidenta live sau din binding documentar explicit, nu prin presupuneri sau copierea alias-ului SSH;
- versiunile documentelor si artefactele de evidenta trebuie sa fie adresabile prin hash, nu doar prin path;
- cheile unice naturale obligatorii in wave-1 sunt cel putin: `cluster_code`, `host_code`, `service_code`, `segment_code`, `document_path`, `source_code`, `run_code`, `policy_code`, `approval_code`, `pack_code`, `template_code`, `request_code`.

## Content: Why This Schema Is Mandatory for Wave-1

Aceasta schema nu este optionala si nu trebuie amanata pentru un „v2 mai curat”, deoarece auditul live a confirmat deja ca infrastructura reala contine simultan:

- noduri fizice si hypervisoare Proxmox;
- runtime-uri Docker dense si hosturi fara Docker;
- servicii shared de observability, AI, IAM, secrets si baze de date;
- expuneri mixte prin Traefik, porturi directe si servicii private;
- retele publice, vSwitch-uri private si bridge-uri de container;
- nevoia de a reconcilia documentele canonice cu observatii runtime si cu contracte de consum pentru servicii shared.

Prin urmare, orice schema mai simpla care reduce modelul la cateva tabele generice cu `JSONB` ar incalca direct blueprint-ul, ar rupe retrieval-ul deterministic si ar introduce ambiguitate exact in zonele pe care platforma trebuie sa le disciplineze.

In plus, blueprint-ul nu cere doar un registry relational si un set de colectori, ci un sistem complet care leaga documentele versionate de chunk-uri, embeddings, evidence packs, broker-e de context, run-uri de agent, aprobari, actiuni si verificari de aplicatie noua. Fara aceste obiecte, planul ar ramane partial si ar descrie doar fundamentul CMDB, nu platforma enterprise integrata ceruta.

## Content: Effective Execution Notes for This Concrete Instance

Pentru aceasta instanta de implementare, ordinea efectiva trebuie sa fie:

1. se pregateste repository-ul local si structura de cod a proiectului `internal_CMDB`;
2. se provisioneaza un runtime PostgreSQL containerizat dedicat pe `orchestrator`, cu Compose separat, cu bind mounts pentru date, backup-uri si exporturi pe `/mnt/HC_Volume_105014654`; accesul extern standard prin Traefik shared la `postgres.orchestrator.neanelu.ro:5432` ramane target-state si trebuie activat doar dupa validarea live a rutarii TCP/SNI, deoarece auditul din 2026-03-08 a observat `connection refused` pe ambele endpoint-uri publice PostgreSQL relevante;
3. se creeaza `internalCMDB`, migrarea initiala si dictionarul de date complet;
4. se implementeaza modelul de securitate minim cerut pentru bootstrap si modelul corect enterprise-grade pentru RLS si expunerea de coloane;
5. se adapteaza scripturile existente din proiect si subproiecte pentru export normalizat;
6. se implementeaza loader-ele locale care scriu in baza de date;
7. se implementeaza `Context Broker`, `Retrieval Broker` si `Action Broker`, cu evidence packs bounded, approval binding si politici explicite pentru read/write;
8. se operationalizeaza chunking-ul documentelor, embeddings-urile locale, registry-ul de prompt templates si ledger-ul de `agent_run` plus `agent_evidence`;
9. se construieste pentru primul pilot setul complet de artefacte canonice: `Research Dossier`, `Application Definition Pack`, `Verification Specification` si `Evidence Map`;
10. se ruleaza backfill-ul initial complet;
11. se valideaza calitatea datelor, se reconciliaza si se aproba baseline-ul;
12. se activeaza KPI-urile, alerting-ul, retention-ul, audit trails si runbook-urile necesare pentru operare enterprise-grade.

Scripturile candidate care trebuie evaluate primele pentru adaptare sunt:

- `subprojects/cluster-full-audit/audit_full.py`;
- `subprojects/cluster-audit/audit_cluster.py`;
- `subprojects/cluster-ssh-checker/test_cluster_ssh.py`;
- `scripts/test_cluster_ssh.py`;
- orice alte scripturi locale care deja extrag inventar, retea, storage, servicii si configuratii.

Ce trebuie implementat explicit in schema `internalCMDB`, fara a lasa goluri pentru mai tarziu:

- entitati pentru hosturi, noduri, VM-uri, containere, servicii shared, instante de servicii, retele, interfete, storage, volume, procese relevante, porturi, politici, ownership si evidenta;
- tabele de relatii pentru depedinte structurale si operationale;
- tabele pentru stare canonica, stare observata, evidenta si provenance;
- tabele pentru `document_chunk`, `chunk_embedding`, `evidence_pack`, `agent_run`, `agent_evidence`, `action_request` si `prompt_template_registry`;
- tabele de taxonomii si controlled vocabularies;
- coloane de lifecycle, confidence, timestamps si source references;
- comentarii de schema si dictionary coverage pentru exploatare enterprise-grade.

Ce nu trebuie facut in aceasta etapa, chiar daca cerinta operationala este urgenta:

- nu se sare peste migrations in favoarea unui bootstrap manual direct in baza de date;
- nu se scriu date brute, ne-normalizate, direct in tabelele finale;
- nu se echivaleaza `RLS pe coloane` cu ceva nativ in PostgreSQL; restrictia de coloane trebuie implementata corect, nu doar declarata;
- nu se lasa bootstrap-ul fara parola ca stare permanenta, chiar daca este acceptat temporar pentru faza initiala;
- nu se foloseste un container PostgreSQL cu tag flotant `latest`, cu volume anonime sau cu persistenta lasata implicit doar in Docker root fara bind mounts explicite;
- nu se publica noul PostgreSQL prin Traefik HTTP si nu se introduce un nou backend PostgreSQL in shared Traefik fara hostname dedicat, regula `HostSNI` separata si validare explicita ca nu afecteaza ruta existenta pentru `postgres.neanelu.ro`.

## Content: Blueprint Gap Closure for Effective Wave-1 Execution

Pentru ca planul sa acopere in mod profesionist si executabil blueprint-ul, wave-1 trebuie sa includa explicit, nu doar declarativ, urmatoarele clase de livrabile.

### 1. Broker-e obligatorii, nu doar intentii de arhitectura

Implementarea wave-1 trebuie sa produca trei componente distincte:

- `Context Broker`, responsabil sa clasifice task-ul, sa aplice filtre de securitate si scope si sa construiasca evidence packs bounded;
- `Retrieval Broker`, responsabil sa execute pipeline-ul corect: exact lookup, metadata filtering, lexical search, semantic retrieval pe subset prefiltrat, reranking si selection rationale;
- `Action Broker`, responsabil sa impuna approval-uri, sa verifice scopul schimbarii, sa inregistreze cererea, sa aplice deny paths si sa capteze rezultatul executiei.

Aceste componente nu pot ramane doar ca reguli narative, deoarece blueprint-ul le cere ca mecanisme centrale ale platformei, nu ca bune intentii. De aceea ele trebuie sa apara explicit in epic-uri, milestone-uri, task-uri, schema de date si modelul de audit.

### 2. Obiecte wave-1 obligatorii pentru retrieval si control plane

Planul wave-1 trebuie sa includa explicit urmatoarele obiecte persistente:

- `document_chunk`, pentru fragmentarea controlata a documentelor canonice;
- `chunk_embedding`, pentru semantic retrieval cu provenance si model versioning;
- `evidence_pack` si `evidence_pack_item`, pentru context assembly bounded si explicabil;
- `prompt_template_registry`, pentru versionarea sabloanelor de prompt aprobate;
- `agent_run`, pentru ledger-ul executiilor agentilor;
- `agent_evidence`, pentru binding explicit intre run-uri, documente, chunks si artefacte observate;
- `action_request`, pentru urmarirea cererilor de actiune si a executiilor intermediate de broker.

Fara aceste obiecte, planul ar modela doar un registry de infrastructura si o documentatie mai buna, nu platforma completa de retrieval grounded si agent governance ceruta de blueprint.

### 3. Artefacte obligatorii pentru orice aplicatie noua

Pentru orice aplicatie noua livrata prin platforma, wave-1 trebuie sa includa task-uri si reguli concrete pentru crearea, aprobarea si binding-ul urmatoarelor artefacte:

- `Research Dossier` ca sursa initiala versionata de fapte, constrangeri si reutilizari;
- `Application Definition Pack` ca pachet canonic complet al aplicatiei;
- `Verification Specification` ca definitie executabila a corectitudinii;
- `Evidence Map` ca legatura dintre afirmatii, surse canonice, registry facts si observatii.

Acestea nu pot ramane doar recomandari de program. Ele trebuie sa devina livrabile obligatorii in track-ul efectiv, altfel pilotul nu valideaza modelul enterprise descris in blueprint.

### 3A. Exemplu concret de mapare pentru primul pilot bounded

Pentru primul pilot wave-1, exemplul recomandat si suficient de bounded este o aplicatie interna read-only de interogare si navigare a `internalCMDB`, folosita de operatori pentru lookup de hosturi, servicii shared, dependinte, evidenta si stare observata. Aceasta alegere este intentionat disciplinata: maximizeaza validarea platformei fara sa introduca inutil complexitate de business externa.

Maparea minima obligatorie a artefactelor pentru acest pilot trebuie sa fie urmatoarea.

`Research Dossier` pentru primul pilot:

- scop: demonstreaza ca exista suficient context real pentru o aplicatie interna de consultare a registry-ului;
- surse canonice minime: blueprint-ul, planul curent, taxonomiile wave-1, contractele pentru PostgreSQL si Traefik shared;
- surse observate minime: auditul live pentru nodurile `hz.*`, topologia Proxmox validata live, serviciile shared observate pe `orchestrator`, runtime-ul PostgreSQL observat pe `postgres-main` si starea curenta a rutelor PostgreSQL relevante, inclusiv probele `connection refused` din 2026-03-08 pentru endpoint-urile publice `:5432`;
- reuse map obligatoriu: ce tabele, ce query packs, ce evidence packs si ce shared services sunt reutilizate fara design nou;
- output obligatoriu: scope bounded, constrangeri de acces, dependinte, riscuri si gap-uri ramase deschise.

`Application Definition Pack` pentru primul pilot:

- `Product Intent Record`: aplicatia ofera interogare read-only pentru `internalCMDB`, cautare de entitati, vizualizare de dependinte si evidenta de provenienta, fara write-path direct in wave-1;
- `Context Boundary Record`: target doar mediul curent, doar clusterul actual si hosturile shared confirmate ca reachable sau marcate explicit ca gap operational, cu acces la `internalCMDB` si fara permisiuni de schimbare infrastructurala;
- `Canonical Domain Model`: entitati principale `cluster`, `host`, `shared_service`, `service_instance`, `network_segment`, `document`, `observed_fact`, `evidence_artifact`;
- `Architecture View Pack`: frontend intern optional minim, API/broker read-only, PostgreSQL `internalCMDB`, retrieval broker pentru evidence packs, observability hooks;
- `Shared Service Contracts`: doua suprafete PostgreSQL distincte trebuie modelate explicit: `postgres-main` ca runtime existent pentru aplicatii, asociat cu `postgres.neanelu.ro`, si runtime-ul dedicat `internalCMDB` planificat pe `orchestrator`, asociat cu `postgres.orchestrator.neanelu.ro`; auditul din 2026-03-08 a confirmat separarea de rol, reachability SSH pentru ambele hosturi si faptul ca ambele endpoint-uri publice `:5432` necesita inca validare operationala, iar Traefik shared si observability shared raman suprafete comune de control si evidenta.

`Verification Specification` pentru primul pilot:

- teste functionale pentru lookup de host dupa `host_code`, `hostname` si IP;
- teste de consistenta pentru traversarea `host -> service_instance -> service_exposure -> evidence_artifact`;
- teste de autorizare care confirma absenta write-path-urilor neaprobate;
- smoke tests pentru retrieval broker pe task-uri read-only de analiza operationala;
- criteriu de acceptanta: orice raspuns al pilotului catre operator trebuie sa poata arata sursa canonica sau observata folosita.

`Evidence Map` pentru primul pilot:

- leaga ecranele sau endpoint-urile pilotului de obiecte precise din registry si de documentele canonice sursa;
- leaga fiecare afirmatie operationala critica de `document_version`, `observed_fact`, `evidence_artifact` sau `agent_evidence`;
- marcheaza explicit unde afirmatia este canonica, observata sau rezultatul unei inferente controlate;
- face imposibila aparitia unui raspuns UI sau API care nu poate fi justificat prin provenance.

### 4. Observability, KPI, retention si runbooks ca livrabile operationale

Wave-1 trebuie sa produca explicit:

- dashboard-uri pentru starea registry-ului, freshness-ul colectorilor, calitatea retrieval-ului si executiile agentilor;
- alerting pentru drift critic, colectori esuati, approval expirate, broker deny paths neasteptate si probleme de ingestie;
- politici de retention pentru audit records, evidence packs, agent runs si artefacte de colectare;
- runbook-uri pentru recovery operational, troubleshooting, reindexare embeddings, rerulare ingestion si investigare a denial-urilor de policy;
- KPI-uri si SLO-uri actionabile, nu doar decorative.

Fara aceste livrabile, planul poate produce componente tehnice, dar nu poate sustine afirmatia ca platforma este operabila enterprise-grade.

### 5. Pozitie onesta privind completitudinea planului

Chiar si dupa extinderea curenta, planul trebuie tratat profesional ca `expanded-enterprise-draft-for-implementation-review`, nu ca document „100% complet si 100% corect” in sens absolut. Motivul este simplu:

- planul depinde in continuare de validari live asupra infrastructurii reale;
- anumite decizii de ownership, approval scopes si sequencing operational trebuie inca inghetate prin executie si review formal;
- orice plan serios pentru un sistem dependent de infrastructura vie trebuie sa accepte delta controlata, nu sa pretinda infailibilitate.

Formularea corecta enterprise-grade este urmatoarea: planul este substantial extins, coerent cu blueprint-ul, executabil pentru wave-1 si suficient de complet pentru a ghida implementarea disciplinata, dar ramane supus revalidarii controlate pe masura ce apar noi fapte live, aprobari sau constrangeri operationale.

## Content: Final Recommendation

Blueprint-ul curent trebuie pastrat ca document de arhitectura tinta. Planul de fata trebuie mentinut separat ca document de executie si program management. Separarea este importanta pentru ca:

- blueprint-ul trebuie sa ramana stabil si conceptual;
- planul trebuie sa poata evolua pe masura ce apar decizii, riscuri, rezultate de pilot si ajustari de sequencing;
- agentii executori au nevoie de reguli operationale si handoff-uri clare, nu doar de viziunea arhitecturala.

Recomandarea operationala actualizata este ca urmatorul handoff sa fie pentru fundatia de executie reala, nu doar pentru taxonomie: ADR pack, ownership matrix, taxonomy v1, metadata schema v1, contractele pentru broker-ele de context si actiune, plus modelul de artefacte pentru pilotul aplicatiei noi. Acesta este punctul in care planul devine executabil fara sa forteze presupuneri majore mai tarziu.
