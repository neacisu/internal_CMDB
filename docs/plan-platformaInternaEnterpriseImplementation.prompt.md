---
name: planPlatformaInternaEnterpriseImplementation
description: Prompt de rafinare pentru planul enterprise al platformei interne, cu metadata structurata completa pastrata in corpul documentului.
---

## Structured Plan Metadata

```yaml
plan_id: platforma-interna-enterprise-v4
plan_type: hybrid
status: draft-for-review
planning_date: 2026-03-08
source_blueprint: /Users/alexneacsu/Documents/ProiecteIT/docs/blueprint_platforma_interna.md
program_name: platforma-interna-enterprise-implementation
implementation_strategy: enterprise-first
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
  - no-write-action-may-bypass-the-action-broker
  - no-context-pack-may-omit-provenance-for-critical-claims
  - no-retrieval-flow-may-start-from-semantic-search-without-structured-filtering-when-structured-data-exists
  - no-registry-record-may-overwrite-canonical-truth-with-observed-state-without-reconciliation-rules
  - every-material-output-must-be-traceable-to-canonical-or-observed-evidence
program_roles:
  executive_sponsor:
    purpose: resolves priorities budget and cross-team escalations
    assignment_rule: must-be-named-before-execution-start
  architecture_board:
    purpose: approves canonical architectural decisions and exception paths
    assignment_rule: must-be-established-in-epic-0
  platform_program_manager:
    purpose: sequencing governance dependency tracking and status reporting
    assignment_rule: must-be-named-before-sprint-1
  platform_architecture_lead:
    purpose: target architecture coherence schema boundaries and integration rules
    assignment_rule: must-be-named-before-epic-1
  platform_engineering_lead:
    purpose: implementation ownership for registry retrieval brokers and runtime packaging
    assignment_rule: must-be-named-before-epic-2
  data_registry_owner:
    purpose: registry data model provenance model migrations and seed quality
    assignment_rule: must-be-named-before-registry-build
  discovery_owner:
    purpose: collectors normalization confidence scoring and freshness guarantees
    assignment_rule: must-be-named-before-epic-3
  security_and_policy_owner:
    purpose: approval model policy engine action restrictions and audit controls
    assignment_rule: must-be-named-before-epic-5
  sre_observability_owner:
    purpose: telemetry alerting retention and operational readiness
    assignment_rule: must-be-named-before-epic-7
  domain_owners:
    purpose: approve canonical facts for infra shared services and applications
    assignment_rule: must-be-declared-per-domain-before-that-domain-is-onboarded
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
```

## Content: Intent and Use of This Plan

Acest document este artefactul de executie al programului, nu blueprint-ul conceptual. Blueprint-ul defineste arhitectura tinta si principiile. Planul de fata defineste ordinea de implementare, responsabilitatile, intrarile, iesirile, criteriile de intrare si iesire, regulile pentru agenti si modul in care se verifica ca implementarea ramane curata, completa si fara presupuneri.

Acest plan trebuie folosit astfel:
- ca referinta program-level pentru ordonarea lucrului pe epics, milestones, sprints si tasks;
- ca document de handoff pentru agenti care implementeaza fiecare pachet de lucru;
- ca baza pentru aprobari, pentru review-uri de progres si pentru decizii de go or no-go;
- ca mecanism de control pentru a preveni derapajele de tip improvizatie, schimbari neauditabile sau extinderi premature de scope.

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

Ce trebuie produs:
- set de KPI-uri si SLO-uri;
- dashboards si alerting;
- politici de retention si acces la audit;
- runbooks operationale;
- readiness review si criterii de wave-2.

Instrucțiuni pentru agenti:
- defineste KPI-uri care ajuta decizii, nu doar raportare decorativa;
- leaga fiecare alert important de un runbook;
- retention-ul trebuie sa acopere atat nevoia de audit, cat si costurile si sensibilitatea datelor;
- readiness review trebuie sa fie bazat pe evidenta acumulata, nu pe optimism privind urmatorul val.

Verificari obligatorii:
- exercitii de alerting pe failure modes relevante;
- sample reviews de audit trails;
- validarea faptului ca high-severity gaps au owner si termen;
- gate review formal pentru extindere.

Criteriu real de terminare:
- exista o baza defensibila pentru decizia de a extinde platforma fara a-i rupe disciplina operationala.

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
- __main__.py, health.py si testele existente ca puncte de plecare pentru conventiile de CLI, health si testare.

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

## Content: Effective Implementation Baseline for This Program

Acest addendum transforma planul din roadmap generic de program in plan de implementare efectiva pentru instanta concreta ceruta acum.

Constrangeri si decizii de executie pentru aceasta implementare:
- dezvoltarea initiala se face local pe macOS, pe masina curenta;
- versionarea sursei se face in Git, cu remote tinta: `https://github.com/neacisu/internal_CMDB.git`;
- runtime-ul PostgreSQL pentru system of record se instaleaza pe hostul `orchestrator.neanelu.ro`, accesat prin `ssh orchestrator`;
- storage-ul persistent pentru runtime-ul PostgreSQL trebuie plasat pe volumul montat la `/mnt/HC_Volume_105014654`;
- baza de date tinta se numeste `internalCMDB`;
- versiunea PostgreSQL trebuie sa fie ultima versiune stabila generala disponibila la momentul executiei pe Debian, validata in ziua instalarii, fara fixare anticipata a unui numar de versiune neverificat in plan;
- bootstrap-ul initial accepta temporar acces administrativ fara parola pentru rolul `postgres`, strict ca exceptie de bootstrap si strict pana la terminarea etapei de seed si validare initiala;
- cerinta exprimata ca `RLS pe toate coloanele` se traduce tehnic astfel: Row Level Security activat pe toate tabelele de business, iar restrictiile la nivel de coloane se implementeaza prin grants, views si schema separation, deoarece PostgreSQL nu implementeaza RLS direct per coloana;
- scripturile existente din repo si subproiecte trebuie tratate ca puncte de pornire pentru colectare si normalizare, nu ca sursa finala neadaptata pentru ingestie enterprise-grade.

## Content: Exact Enterprise Delivery Track for Effective Implementation

Acest track completeaza planul de program de mai sus si defineste implementarea efectiva a primei instante operationale.

```yaml
effective_delivery_track:
  track_id: effective-wave-1-internal-cmdb
  objective: >-
    Implementarea efectiva a primei instante a platformei interne sub forma
    internalCMDB, cu dezvoltare locala pe macOS, versionare in Git, PostgreSQL
    operational pe orchestrator si ingestie initiala a infrastructurii reale din
    activele si scripturile existente in repo.
  implementation_topology:
    development_host:
      type: local-macos-workstation
      purpose: source-authoring-migrations-testing-and-adapter-development
    source_control:
      vcs: git
      remote_url: https://github.com/neacisu/internal_CMDB.git
      branching_rule: trunk-based-with-short-lived-feature-branches
    target_database_host:
      ssh_alias: orchestrator
      fqdn: orchestrator.neanelu.ro
      os: debian-linux
      persistence_mount: /mnt/HC_Volume_105014654
      persistence_requirement: postgresql-data-root-must-live-on-mounted-volume
    target_database:
      name: internalCMDB
      engine: postgresql-latest-stable-at-execution-date
      bootstrap_admin_role: postgres
      bootstrap_auth_mode: temporary-no-password-exception
      bootstrap_exception_rule: remove-or-restrict-after-initial-bootstrap-phase
    security_translation:
      requested_rule: rls-on-all-columns
      actual_implementation_rule: rls-on-all-business-tables-plus-column-restriction-via-views-grants-and-schema-boundaries
  effective_epics:
    - id: impl-epic-1
      name: local-workspace-and-repository-bootstrap
      objective: establish the local engineering baseline and bind it to the dedicated Git repository
      outcome: reproducible local development workspace linked to the internal_CMDB repository
    - id: impl-epic-2
      name: orchestrator-postgresql-foundation
      objective: provision the database host runtime, storage layout and PostgreSQL service on orchestrator
      outcome: running PostgreSQL instance backed by the mounted persistent volume
    - id: impl-epic-3
      name: internalcmdb-enterprise-schema-and-taxonomy
      objective: design and implement the full database structure, taxonomies and migrations for internalCMDB
      outcome: enterprise-grade schema, migration chain and taxonomy reference model
    - id: impl-epic-4
      name: security-model-roles-and-access-boundaries
      objective: implement bootstrap access, table-level RLS, column exposure controls and operational access patterns
      outcome: enforceable access model compatible with the blueprint and the requested bootstrap posture
    - id: impl-epic-5
      name: discovery-adapters-normalization-and-initial-backfill
      objective: adapt or create local scripts that discover real infrastructure facts and write normalized records into internalCMDB
      outcome: first full backfill of real infrastructure data into the registry
    - id: impl-epic-6
      name: validation-reconciliation-and-operational-readiness
      objective: validate data quality, verify taxonomy coverage, reconcile observed facts and prepare the platform for continued evolution
      outcome: auditable and queryable first production-capable registry baseline
  effective_milestones:
    - id: impl-m1
      epic_id: impl-epic-1
      name: repository-and-local-toolchain-ready
      acceptance: local repo initialized or linked to remote, Python toolchain validated, migration tooling selected
    - id: impl-m2
      epic_id: impl-epic-2
      name: orchestrator-storage-and-postgresql-ready
      acceptance: PostgreSQL installed on orchestrator, data directory persisted on target volume, service health validated
    - id: impl-m3
      epic_id: impl-epic-3
      name: logical-data-model-approved
      acceptance: entity model, taxonomy hierarchy and naming conventions frozen for wave-1
    - id: impl-m4
      epic_id: impl-epic-3
      name: migration-chain-v1-ready
      acceptance: initial schema migrations apply cleanly from empty database to current head
    - id: impl-m5
      epic_id: impl-epic-4
      name: security-controls-v1-active
      acceptance: business tables protected with RLS and column exposure restrictions implemented
    - id: impl-m6
      epic_id: impl-epic-5
      name: source-adapters-defined
      acceptance: extractor contracts agreed for all wave-1 discovery sources
    - id: impl-m7
      epic_id: impl-epic-5
      name: normalized-ingestion-live
      acceptance: local scripts can write normalized records into internalCMDB without manual SQL intervention
    - id: impl-m8
      epic_id: impl-epic-5
      name: first-full-backfill-complete
      acceptance: all currently reachable machines and key services are represented in the registry
    - id: impl-m9
      epic_id: impl-epic-6
      name: data-quality-and-reconciliation-reviewed
      acceptance: duplicates, missing bindings and inconsistent taxonomies are reviewed and corrected
    - id: impl-m10
      epic_id: impl-epic-6
      name: operational-baseline-approved
      acceptance: internalCMDB can be used as the first authoritative operational registry baseline for continued platform work
  effective_sprints:
    - id: impl-sprint-1
      duration: 1-week
      goal: local bootstrap and repository binding
      milestone_ids: [impl-m1]
    - id: impl-sprint-2
      duration: 1-week
      goal: orchestrator PostgreSQL provisioning and persistent storage setup
      milestone_ids: [impl-m2]
    - id: impl-sprint-3
      duration: 2-weeks
      goal: schema design taxonomy definition and migration authoring
      milestone_ids: [impl-m3, impl-m4]
    - id: impl-sprint-4
      duration: 1-week
      goal: access model RLS and view-based exposure controls
      milestone_ids: [impl-m5]
    - id: impl-sprint-5
      duration: 2-weeks
      goal: extractor adaptation normalization and first ingestion
      milestone_ids: [impl-m6, impl-m7]
    - id: impl-sprint-6
      duration: 1-to-2-weeks
      goal: full backfill validation reconciliation and operational sign-off
      milestone_ids: [impl-m8, impl-m9, impl-m10]
  effective_tasks:
    - id: impl-t-001
      sprint_id: impl-sprint-1
      epic_id: impl-epic-1
      name: initialize-or-link-local-repository-to-internal_cmdb-remote
      deliverable: local working tree bound to github remote and documented bootstrap steps
    - id: impl-t-002
      sprint_id: impl-sprint-1
      epic_id: impl-epic-1
      name: define-local-project-layout-for-schema-migrations-loaders-and-taxonomies
      deliverable: agreed directory layout for migrations models taxonomies loaders and tests
    - id: impl-t-003
      sprint_id: impl-sprint-1
      epic_id: impl-epic-1
      name: select-and-bootstrap-migration-framework
      deliverable: migration tool integrated locally with repeatable upgrade and downgrade commands
    - id: impl-t-004
      sprint_id: impl-sprint-1
      epic_id: impl-epic-1
      name: define-environment-configuration-model
      deliverable: local and remote configuration contract for connection strings paths and execution modes
    - id: impl-t-005
      sprint_id: impl-sprint-2
      epic_id: impl-epic-2
      name: validate-orchestrator-storage-layout-on-mounted-volume
      deliverable: approved data-root layout under mounted volume for PostgreSQL data backups and exports
    - id: impl-t-006
      sprint_id: impl-sprint-2
      epic_id: impl-epic-2
      name: install-latest-stable-postgresql-on-orchestrator
      deliverable: PostgreSQL service installed from the latest stable package source available at execution time
    - id: impl-t-007
      sprint_id: impl-sprint-2
      epic_id: impl-epic-2
      name: relocate-postgresql-data-directory-to-persistent-volume
      deliverable: active PostgreSQL cluster storing data on the target mounted volume
    - id: impl-t-008
      sprint_id: impl-sprint-2
      epic_id: impl-epic-2
      name: create-internalcmdb-database-and-bootstrap-admin-access
      deliverable: database internalCMDB created with temporary bootstrap administrative access as requested
    - id: impl-t-009
      sprint_id: impl-sprint-3
      epic_id: impl-epic-3
      name: derive-enterprise-taxonomy-from-blueprint-and-current-infrastructure
      deliverable: taxonomy hierarchy for infrastructure services ownership states evidence and relations
    - id: impl-t-010
      sprint_id: impl-sprint-3
      epic_id: impl-epic-3
      name: define-core-entity-model-for-hosts-services-instances-networks-storage-and-applications
      deliverable: logical entity model with identifiers relationships lifecycle and provenance fields
    - id: impl-t-011
      sprint_id: impl-sprint-3
      epic_id: impl-epic-3
      name: define-supporting-reference-tables-and-enumeration-taxonomies
      deliverable: reference taxonomy tables and controlled vocabularies for normalized ingestion
    - id: impl-t-012
      sprint_id: impl-sprint-3
      epic_id: impl-epic-3
      name: author-initial-schema-migrations-for-all-wave-1-tables
      deliverable: first complete migration chain for schemas tables indexes constraints comments and seed reference data
    - id: impl-t-013
      sprint_id: impl-sprint-3
      epic_id: impl-epic-3
      name: create-db-comments-and-data-dictionary-coverage
      deliverable: database comments and accompanying dictionary for every core table and column
    - id: impl-t-014
      sprint_id: impl-sprint-4
      epic_id: impl-epic-4
      name: classify-business-tables-and-enable-rls-on-each
      deliverable: RLS enabled on every business table that stores operational records
    - id: impl-t-015
      sprint_id: impl-sprint-4
      epic_id: impl-epic-4
      name: implement-view-based-column-exposure-model
      deliverable: restricted views and grants for sensitive columns and role-specific read surfaces
    - id: impl-t-016
      sprint_id: impl-sprint-4
      epic_id: impl-epic-4
      name: define-bootstrap-security-exception-and-hardening-followup
      deliverable: explicit record of temporary no-password bootstrap posture and mandatory hardening task list
    - id: impl-t-017
      sprint_id: impl-sprint-5
      epic_id: impl-epic-5
      name: inventory-existing-scripts-that-can-feed-discovery
      deliverable: source inventory covering local scripts and subproject scripts reusable for extraction
    - id: impl-t-018
      sprint_id: impl-sprint-5
      epic_id: impl-epic-5
      name: define-normalization-contracts-between-script-output-and-database-schema
      deliverable: canonical loader contract mapping raw script fields to target tables and taxonomies
    - id: impl-t-019
      sprint_id: impl-sprint-5
      epic_id: impl-epic-5
      name: adapt-audit_full-and-related-auditors-into-loader-compatible-producers
      deliverable: normalized machine facts exported in a structured format ready for database loading
    - id: impl-t-020
      sprint_id: impl-sprint-5
      epic_id: impl-epic-5
      name: implement-local-loader-scripts-for-upsert-into-internalcmdb
      deliverable: local loader scripts that create or update normalized registry records
    - id: impl-t-021
      sprint_id: impl-sprint-5
      epic_id: impl-epic-5
      name: implement-provenance-capture-on-every-ingested-record
      deliverable: source timestamp collector identifier and execution context persisted with each load batch
    - id: impl-t-022
      sprint_id: impl-sprint-5
      epic_id: impl-epic-5
      name: run-first-targeted-ingestion-for-priority-machines
      deliverable: first verified subset of orchestrator and related machines written into internalCMDB
    - id: impl-t-023
      sprint_id: impl-sprint-6
      epic_id: impl-epic-5
      name: execute-full-wave-1-backfill-of-reachable-machines-and-core-services
      deliverable: first complete inventory load for all currently reachable infrastructure assets in scope
    - id: impl-t-024
      sprint_id: impl-sprint-6
      epic_id: impl-epic-6
      name: validate-row-counts-relations-nullability-and-taxonomy-coverage
      deliverable: data quality report with coverage gaps duplicates and relation anomalies
    - id: impl-t-025
      sprint_id: impl-sprint-6
      epic_id: impl-epic-6
      name: reconcile-observed-facts-with-blueprint-driven-canonical-model
      deliverable: reconciliation report highlighting mismatches missing bindings and taxonomy gaps
    - id: impl-t-026
      sprint_id: impl-sprint-6
      epic_id: impl-epic-6
      name: create-operational-query-pack-for-internalcmdb
      deliverable: curated SQL and CLI query pack for hosts services dependencies evidence and ownership lookups
    - id: impl-t-027
      sprint_id: impl-sprint-6
      epic_id: impl-epic-6
      name: document-next-hardening-step-for-postgres-authentication
      deliverable: explicit post-bootstrap hardening plan for passwords auth methods roles and network exposure
    - id: impl-t-028
      sprint_id: impl-sprint-6
      epic_id: impl-epic-6
      name: approve-internalcmdb-as-wave-1-registry-baseline
      deliverable: sign-off record that the first operational baseline is usable for continued platform build-out
```

## Content: Effective Execution Notes for This Concrete Instance

Pentru aceasta instanta de implementare, ordinea efectiva trebuie sa fie:
1. se pregateste repository-ul local si structura de cod a proiectului `internal_CMDB`;
2. se provisioneaza PostgreSQL pe `orchestrator`, cu datele persistate pe `/mnt/HC_Volume_105014654`;
3. se creeaza `internalCMDB`, migrarea initiala si dictionarul de date complet;
4. se implementeaza modelul de securitate minim cerut pentru bootstrap si modelul corect enterprise-grade pentru RLS si expunerea de coloane;
5. se adapteaza scripturile existente din proiect si subproiecte pentru export normalizat;
6. se implementeaza loader-ele locale care scriu in baza de date;
7. se ruleaza backfill-ul initial complet;
8. se valideaza calitatea datelor, se reconciliaza si se aproba baseline-ul.

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
- tabele de taxonomii si controlled vocabularies;
- coloane de lifecycle, confidence, timestamps si source references;
- comentarii de schema si dictionary coverage pentru exploatare enterprise-grade.

Ce nu trebuie facut in aceasta etapa, chiar daca cerinta operationala este urgenta:
- nu se sare peste migrations in favoarea unui bootstrap manual direct in baza de date;
- nu se scriu date brute, ne-normalizate, direct in tabelele finale;
- nu se echivaleaza `RLS pe coloane` cu ceva nativ in PostgreSQL; restrictia de coloane trebuie implementata corect, nu doar declarata;
- nu se lasa bootstrap-ul fara parola ca stare permanenta, chiar daca este acceptat temporar pentru faza initiala.

## Content: Final Recommendation

Blueprint-ul curent trebuie pastrat ca document de arhitectura tinta. Planul de fata trebuie mentinut separat ca document de executie si program management. Separarea este importanta pentru ca:
- blueprint-ul trebuie sa ramana stabil si conceptual;
- planul trebuie sa poata evolua pe masura ce apar decizii, riscuri, rezultate de pilot si ajustari de sequencing;
- agentii executori au nevoie de reguli operationale si handoff-uri clare, nu doar de viziunea arhitecturala.

Recomandarea operationala este ca urmatorul handoff sa fie pentru epic-0 si epic-1 in paralel controlat, cu livrabil explicit: ADR pack, ownership matrix, taxonomy v1 si metadata schema v1. Acesta este punctul in care planul devine executabil fara sa forteze presupuneri majore mai tarziu.
