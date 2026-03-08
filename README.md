# internal_CMDB

`internal_CMDB` este repo-ul de lucru pentru prima implementare a registry-ului operațional descris în blueprint-ul platformei interne. Scopul imediat este construirea unui nucleu PostgreSQL-first pentru `internalCMDB`, cu model relațional pentru infrastructură, servicii shared, ownership, provenance și stare observată, plus scripturi de discovery și load controlat.

În forma actuală, repo-ul păstrează și baseline-ul Python existent din care se va construi CLI-ul, verificările locale și utilitarele de ingestie.

## Scope curent

- bază de cod Python pentru CLI, health checks și utilitare de încărcare
- planul enterprise de implementare din `docs/`
- scripturi existente de audit și discovery care vor fi adaptate pentru ingestie în `internalCMDB`
- standarde stricte de calitate: `ruff`, `mypy`, `pytest`, `bandit`, `pip-audit`

## Target operațional

- dezvoltare locală pe macOS
- versionare în Git și lucru pe branch-uri scurte, nu direct în `main`
- PostgreSQL instalat pe `orchestrator.neanelu.ro`
- date persistate pe `/mnt/HC_Volume_105014654`
- bază de date țintă: `internalCMDB`

## Quick Start

```bash
./scripts/bootstrap.sh
source .venv/bin/activate
make check
```

## Comenzi uzuale

```bash
make lint
make type
make test
make security
make audit
make check
make build
```

## Structura repo-ului

```text
src/proiecteit/       # pachetul Python existent pentru CLI și health checks
tests/                # teste unitare
docs/                 # blueprint și planul enterprise de implementare
scripts/              # bootstrap și automatizări locale
subprojects/          # utilitare și active tehnice reutilizabile pentru discovery
```

## Documente cheie

- `docs/blueprint_platforma_interna.md` definește arhitectura țintă
- `docs/plan-platformaInternaEnterpriseImplementation.prompt.md` definește track-ul efectiv de implementare pentru prima instanță `internalCMDB`

## Reguli de lucru

- schimbările se fac pe branch-uri de lucru dedicate și se integrează prin review
- nu se fac modificări direct în `main`
- bootstrap-ul inițial PostgreSQL poate folosi excepția temporară pentru `postgres`, dar hardening-ul rămâne obligatoriu după seed-ul inițial
- datele observate se normalizează înainte de ingestie; nu se scriu brute direct în tabelele finale

## Următorul pas logic

Primul val de implementare trebuie să producă structura repo-ului pentru `internal_CMDB`, lanțul de migrations și bootstrap-ul PostgreSQL pe `orchestrator`, apoi adaptoarele de discovery pentru încărcarea infrastructurii reale.
