# Inventar complet: Probleme & Rezolvări — internalCMDB

> Audit efectuat: 2026-04-07  
> Tooluri rulate: ruff, bandit, semgrep (auto config), yamllint, eslint, tsc, pytest (colecție), pip-audit (parțial), mypy (indisponibil)  
> Metodă: fiecare problemă a fost verificată prin citirea codului sursă înainte de formularea soluției.  
> **Versiune 2** — adăugat audit frontend (ESLint 37 erori), infrastructure/CI (4 probleme), sintaxă Python 3.14, test suite.

---

## Cuprins

### Backend Python
1. [REAL — Concatenare SQL fără validarea `child` în retention.py](#1-real--concatenare-sql-fără-validarea-child-în-retentionpy)
2. [REAL — Excepție înghițită silențios în data_quality.py](#2-real--excepție-înghițită-silențios-în-data_qualitypy)
3. [REAL — JTI logat complet în revocation.py](#3-real--jti-logat-în-revocationpy)
4. [REAL — SyntaxError în observability/logging.py pe Python ≤ 3.13](#4-real--syntaxerror-în-observabilityloggingpy-pe-python--313)
5. [REAL — 44 erori ruff în subprojects/](#5-real--44-erori-ruff-în-subprojects)
6. [REAL — Bandit nu poate analiza 22 fișiere Python 3.14 — cauza reală](#6-real--bandit-nu-poate-analiza-22-fișiere-python-314)
7. [REAL — Mypy și pip-audit indisponibile în mediul de CI curent](#7-real--mypy-și-pip-audit-indisponibile-în-mediul-de-ci-curent)

### Frontend TypeScript / React
8. [REAL — kpi-card.tsx: acces și mutare ref în timpul render-ului](#8-real--kpi-cardtsx-acces-și-mutare-ref-în-timpul-render-ului)
9. [REAL — 7 paneluri Settings: setState apelat sincron în useEffect](#9-real--7-paneluri-settings-setstate-apelat-sincron-în-useeffect)
10. [REAL — useWebSocket.ts: auto-referință ilegală și dependency lipsă](#10-real--usewebsocketts-auto-referință-ilegală-și-dependency-lipsă)
11. [REAL — hooks.ts: Date.now() apelat în timpul render-ului](#11-real--hooksts-datenow-apelat-în-timpul-render-ului)
12. [REAL — 2 variabile importate/declarate dar neutilizate în production code](#12-real--2-variabile-importatedeclarate-dar-neutilizate-în-production-code)
13. [REAL — 17 componente fără displayName în fișiere de test](#13-real--17-componente-fără-displayname-în-fișiere-de-test)

### Infrastructure / CI / Docker
14. [REAL — --forwarded-allow-ips "*" în Dockerfile.api](#14-real----forwarded-allow-ips--în-dockerfileapi)
15. [REAL — Node.js 25 în Dockerfile vs Node.js 22 în CI](#15-real--nodejs-25-în-dockerfile-vs-nodejs-22-în-ci)
16. [REAL — Semgrep community scan nu blochează CI la findings](#16-real--semgrep-community-scan-nu-blochează-ci-la-findings)
17. [REAL — Test suite nu poate rula în mediul curent (42 erori colecție)](#17-real--test-suite-nu-poate-rula-în-mediul-curent-42-erori-colecție)
18. [REAL — Erori structurale YAML în fișiere deploy/](#18-real--erori-structurale-yaml-în-fișiere-deploy)

### False Positives documentate
19. [FALSE POSITIVE — tarfile path traversal în updater.py](#19-false-positive--tarfile-path-traversal-în-updaterpy)
20. [FALSE POSITIVE — XSS în rate_limit.py](#20-false-positive--xss-în-rate_limitpy)
21. [FALSE POSITIVE — Credential disclosure în logs (majority)](#21-false-positive--credential-disclosure-în-logs-majority)
22. [FALSE POSITIVE — 130× avoid-sqlalchemy-text în migrations/](#22-false-positive--130-avoid-sqlalchemy-text-în-migrations)
23. [FALSE POSITIVE — SQL concatenare în debug.py, settings.py, cognitive/](#23-false-positive--sql-concatenare-în-debugpy-settingspy-cognitive)
24. [INFORMATIONAL — try/except/pass intenționate](#24-informational--tryexceptpass-intenționate)
11. [FALSE POSITIVE — 130× avoid-sqlalchemy-text în migrations/](#11-false-positive--130-avoid-sqlalchemy-text-în-migrations)
12. [FALSE POSITIVE — SQL concatenare în debug.py, settings.py, cognitive/](#12-false-positive--sql-concatenare-în-debugpy-settingspy-cognitive)
13. [INFORMATIONAL — try/except/pass intenționate](#13-informational--tryexceptpass-intenționate)

---

## 1. REAL — Concatenare SQL fără validarea `child` în retention.py

### Fișiere
- `src/internalcmdb/workers/retention.py:118–130`

### Descrierea problemei

În funcția `_drop_old_partitions`, numele partițiilor (`child`) este obținut dintr-un query pe catalogul PostgreSQL (`pg_inherits`) și este concatenat direct în SQL fără a trece prin `_validate_identifier`:

```python
# retenion.py:118–130
for (child,) in rows:
    ...
    check_sql = (
        "SELECT EXISTS (SELECT 1 FROM "
        + child                          # ← fără _validate_identifier
        + " WHERE "
        + ts_column
        + " >= NOW() - INTERVAL :retention_interval LIMIT 1)"
    )
    result = conn.execute(text(check_sql), {"retention_interval": interval})
    ...
    drop_sql = "DROP TABLE IF EXISTS " + child   # ← fără _validate_identifier
    conn.execute(text(drop_sql))
```

Prin contrast, `_delete_old_rows` (linia 137–138) apelează `_validate_identifier` pentru `table` și `ts_column` înainte de concatenare — pattern inconsistent.

### De ce e o problemă reală

`child` vine din `pg_inherits`, deci în practică conține doar nume valide de tabele (PostgreSQL impune reguli de naming la `CREATE TABLE`). Totuși:

1. **Inconsistență de apărare-în-adâncime**: restul funcțiilor validează explicit, aceasta nu.
2. **Suprafață de atac indirectă**: dacă vreodată `_drop_old_partitions` primește date din altă sursă (refactorizare, mock de test), lipsa validării devine o vulnerabilitate reală.
3. Bandit (B608) și semgrep (`avoid-sqlalchemy-text`) flaghează acest loc cu motiv legitim.

### Rezolvare

Adăugarea validării explicit pentru `child` **înainte** de concatenare, identic cu pattern-ul existent în `_delete_old_rows`:

```python
# retention.py — în _drop_old_partitions, după linia 113
for (child,) in rows:
    if total_partitions - dropped <= 1:
        logger.info("Keeping last partition %s for %s", child, parent_table)
        break

    _validate_identifier(child, "child_partition")   # ← adăugat

    check_sql = (
        "SELECT EXISTS (SELECT 1 FROM "
        + child
        + " WHERE "
        + ts_column
        + " >= NOW() - INTERVAL :retention_interval LIMIT 1)"
    )
    result = conn.execute(text(check_sql), {"retention_interval": interval})
    has_recent = result.scalar()
    if not has_recent:
        logger.info("Dropping expired partition %s", child)
        drop_sql = "DROP TABLE IF EXISTS " + child
        conn.execute(text(drop_sql))
        dropped += 1
```

`_validate_identifier` există deja în același fișier (linia 61–64) și ridică `ValueError` dacă numele nu corespunde regex-ului `^[a-z_][a-z0-9_.]{0,62}$`. Nu este necesar cod nou.

---

## 2. REAL — Excepție înghițită silențios în data_quality.py

### Fișiere
- `src/internalcmdb/cognitive/data_quality.py:365–378`

### Descrierea problemei

Metoda care citește hosturi din baza de date înghite silențios orice excepție și returnează date sintetice (fake) fără să logheze eroarea:

```python
# data_quality.py:365–378
if self._session is not None:
    try:
        from sqlalchemy import text as sa_text

        result = await self._session.execute(
            sa_text("SELECT * FROM registry.host LIMIT 500")
        )
        rows = result.fetchall()
        return [dict(r._mapping) for r in rows]
    except Exception:
        pass    # ← excepție înghițită, fără log

return [
    {"host_code": "prod-gpu-01", ...},   # date sintetice hardcodate
    {"host_code": "prod-gpu-02", ...},
    ...
]
```

### De ce e o problemă reală

Dacă sesiunea de bază de date este validă (nu `None`) dar query-ul eșuează — din orice cauză (tabelul nu există, conexiune pierdută, timeout, schema incorectă) — funcția returnează **silențios date sintetice de test** ca și cum ar fi date reale. Componenta care apelează funcția nu știe că a primit date false. Aceasta poate corupe analiza de calitate a datelor în producție fără niciun semnal de avertizare în loguri.

### Rezolvare

Logarea excepției la nivel `WARNING` înainte de fallback, fără a schimba comportamentul de fallback (care poate fi intenționat pentru medii fără bază de date):

```python
if self._session is not None:
    try:
        from sqlalchemy import text as sa_text

        result = await self._session.execute(
            sa_text("SELECT * FROM registry.host LIMIT 500")
        )
        rows = result.fetchall()
        return [dict(r._mapping) for r in rows]
    except Exception:
        logger.warning(
            "Failed to fetch hosts from registry.host — falling back to synthetic data",
            exc_info=True,
        )

return [...]   # fallback sintetic
```

`logger` este deja importat în fișier. `exc_info=True` include stack trace-ul complet în log, esențial pentru diagnosticare.

---

## 3. REAL — JTI logat în revocation.py

### Fișiere
- `src/internalcmdb/auth/revocation.py:46, 52, 62, 68`

### Descrierea problemei

JWT Token ID (`jti`) este logat în patru locuri:

```python
# revocation.py:46
logger.warning("Redis unavailable — token revocation skipped for jti=%s", jti)
# revocation.py:52
logger.warning("Redis error — token revocation skipped for jti=%s", jti, exc_info=True)
# revocation.py:62
logger.warning("Redis unavailable — revocation check skipped for jti=%s", jti)
# revocation.py:68
logger.warning("Redis error — revocation check skipped for jti=%s", jti, exc_info=True)
```

### Evaluare exactă

Un `jti` este un UUID unic care identifică un token specific. Singur, nu poate fi folosit să forjeze un token nou — nu conține secretul de semnare. Totuși:

- Cineva cu acces la fișierele de log poate **enumera JTI-urile active** și le poate folosi pentru a verifica dacă un anumit token a fost revocat (prin interogare directă Redis cu prefixul `auth:revoked:`).
- Dacă sistemul de logging nu este protejat (ex: log aggregation neautentificat), aceste JTI-uri devin metadate despre sesiunile utilizatorilor.
- Semgrep flaghează corect pattern-ul (`python-logger-credential-disclosure`, CWE-532).

### Rezolvare

Truncherea JTI-ului în mesajele de log la primele 8 caractere — suficient pentru debugging, insuficient pentru enumerare:

```python
# revocation.py — pattern aplicat consistent în toate cele 4 locuri

def revoke_token(jti: str, expires_at: datetime) -> None:
    ...
    client = _redis_client()
    if client is None:
        logger.warning("Redis unavailable — token revocation skipped for jti=%.8s…", jti)
        return

    try:
        client.setex(f"{_PREFIX}{jti}", remaining, "1")
    except Exception:
        logger.warning("Redis error — token revocation skipped for jti=%.8s…", jti, exc_info=True)


def is_revoked(jti: str) -> bool:
    client = _redis_client()
    if client is None:
        logger.warning("Redis unavailable — revocation check skipped for jti=%.8s…", jti)
        return False

    try:
        return bool(client.exists(f"{_PREFIX}{jti}"))
    except Exception:
        logger.warning("Redis error — revocation check skipped for jti=%.8s…", jti, exc_info=True)
        return False
```

`%.8s` este format specifier standard Python pentru string trunchiat la 8 caractere. Funcționează direct în `logger.warning(format, arg)` fără modificarea șirului `jti` în memorie.

---

## 4. REAL — Erori structurale YAML în fișiere deploy/

### 4a. `deploy/orchestrator/docker-compose.postgresql.yml:23–26`

**Problema:** yamllint raportează `too many spaces after colon` pe liniile cu variabilele de environment:

```yaml
# liniile 23–26 din fișier
environment:
  POSTGRES_DB:       ${POSTGRES_DB:-internalCMDB}   # ← 7 spații extra
  POSTGRES_USER:     ${POSTGRES_USER:-internalcmdb} # ← 5 spații extra
  POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
  PGDATA:            /var/lib/postgresql/data/pgdata # ← 12 spații extra
```

Standardul YAML (și yamllint cu regula `colons`) impune exact un spațiu după `:`. Alinierea vizuală nu este validă YAML strict.

**Context:** Docker Compose parsează fișierul corect deoarece folositorul propriu de YAML este mai permisiv. Dar linters, validatoare CI și unele orchestratoare stricte pot respinge fișierul.

**Rezolvare:** eliminarea spațiilor de aliniere suplimentare:

```yaml
environment:
  POSTGRES_DB: ${POSTGRES_DB:-internalCMDB}
  POSTGRES_USER: ${POSTGRES_USER:-internalcmdb}
  POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
  PGDATA: /var/lib/postgresql/data/pgdata
```

### 4b. `deploy/wapp-pro-app/docker-compose.yml:25, 51, 75, 96`

**Problema:** yamllint raportează `too many spaces inside braces` pe liniile cu opțiunile de logging:

```yaml
# liniile 25, 51, 75, 96 — pattern identic
logging:
  driver: json-file
  options: { max-size: "20m", max-file: "5" }
#          ^                               ^
#          spații după { și înainte de }
```

Regula yamllint `braces` cu `forbid-flows-in-block-mappings` sau spațiere strictă refuză spații imediat după `{` sau înainte de `}` în flow mappings.

**Rezolvare — opțiunea 1 (flow mapping fără spații suplimentare):**

```yaml
logging:
  driver: json-file
  options: {max-size: "20m", max-file: "5"}
```

**Rezolvare — opțiunea 2 (block mapping, mai lizibil):**

```yaml
logging:
  driver: json-file
  options:
    max-size: "20m"
    max-file: "5"
```

Opțiunea 2 este mai bună stilistic și nu poate genera ambiguități de parsing.

---

## 5. REAL — 44 erori ruff în subprojects/

### Context

Toate cele 44 erori sunt în directorul `subprojects/`, nu în `src/internalcmdb/`. Codul principal este curat din perspectiva ruff.

### Clasificare și rezolvare per categorie

#### F401 — 13 importuri neutilizate (auto-fixabile)

Fișiere afectate: `test_audit_cluster.py`, `test_allow_cluster_ips.py`, `test_mesh_keys.py`, `test_audit_result_store.py`, `test_audit_trust_surface.py`, `test_audit_full.py` și altele.

Pattern repetat: `import pytest` și `from unittest.mock import MagicMock, patch` importate dar neutilizate.

```bash
# Rezolvare automată:
ruff check subprojects/ --fix --select F401
```

Sau manual, ștergerea liniilor cu import neutilizat din fiecare fișier de test.

#### I001 — 8 blocuri de importuri nesortate (auto-fixabile)

Apare în fișierele de test ale subproiectelor unde `sys.path.insert(...)` este intercalat cu importurile third-party, invalidând ordinea isort.

```bash
ruff check subprojects/ --fix --select I001
```

#### PLR2004 — 15 comparații cu magic values (în teste)

Exemple:
```python
assert _as_int("42") == 42          # test_audit_full.py:33
assert len(logs) == 3               # test_allow_cluster_ips.py:91
assert len(CLUSTER) == 9            # test_allow_cluster_ips.py:166
```

Rezolvare: extragerea valorilor în constante numite la nivel de modul în fiecare fișier de test:

```python
# test_allow_cluster_ips.py — exemplu
_EXPECTED_LOG_COUNT = 3
_EXPECTED_CLUSTER_SIZE = 9

assert len(logs) == _EXPECTED_LOG_COUNT
assert len(CLUSTER) == _EXPECTED_CLUSTER_SIZE
```

Alternativ, dacă valorile sunt verificări ale unor constante definite în modulul testat (ex: `len(CLUSTER) == 9`), testul ar trebui să reflecte intenția:
```python
# mai expresiv decât comparația cu magic value
assert len(CLUSTER) == _CLUSTER_SIZE_EXPECTED
```

#### PLC0415 — 5 importuri în interiorul funcțiilor

```python
# test_allow_cluster_ips.py:170
def test_cluster_ips_are_valid_format() -> None:
    import re   # ← import la nivel de funcție
```

```python
# test_audit_trust_surface.py:206, 208, 223, 235
def test_audit_host_returns_error_on_timeout() -> None:
    import subprocess           # ← import la nivel de funcție
    from audit_trust_surface import audit_host   # ← import la nivel de funcție
```

Rezolvare: mutarea importurilor la nivel de modul (top-level), unde aparțin conform convenției Python:

```python
# test_audit_trust_surface.py — la top
import subprocess
from audit_trust_surface import audit_host, ...
```

Excepție acceptabilă: importuri circulare sau importuri condiționate de disponibilitatea unui modul opțional. În fișierele de test din subprojects nu există această situație.

#### E501 — 1 linie prea lungă

```
subprojects/cluster-key-mesh/mesh_keys.py:131 (114 > 100 caractere)
```

Este un comentariu de documentare a plasamentului LXC:
```python
#   hz.215 (NewCluster Node 3): LXC 105 (wapp-pro-app), 111 (neanelu-prod), 112 (neanelu-staging), 115 (llm-guard)
```

Rezolvare: împărțirea comentariului pe două linii:
```python
#   hz.215 (NewCluster Node 3): LXC 105 (wapp-pro-app), 111 (neanelu-prod),
#                               LXC 112 (neanelu-staging), 115 (llm-guard)
```

#### RUF059 — 1 variabilă despachetată neutilizată

```python
# test_allow_cluster_ips.py:152
alias, fw, logs = process_node("hz.113", ["10.0.1.1"])
# ^--- 'alias' nu este folosit în test
```

Rezolvare:
```python
_, fw, logs = process_node("hz.113", ["10.0.1.1"])
```

#### RUF100 — 1 directivă noqa inutilă

```python
# scripts/load_test.py:28
print(  # noqa: T201
```

`T201` (print statement) nu este activat în configurația ruff a proiectului (regula nu face parte din selected rules), deci `# noqa: T201` nu face nimic.

Rezolvare: ștergerea comentariului `# noqa: T201` de pe linia 28.

---

## 6. REAL — Bandit nu poate analiza 22 fișiere Python 3.14

### Problema

Bandit 1.9.4 folosește AST-ul Python-ului cu care rulează (Python 3.13) pentru a parsa fișierele analizate. Cele 22 fișiere din `src/internalcmdb/` care folosesc sintaxă introdusă în Python 3.14 (sau specifică implementărilor 3.14-dev) nu pot fi parsate și sunt **complet excluse din analiză**:

```
src/internalcmdb/api/routers/metrics_live.py
src/internalcmdb/cognitive/correlator.py
src/internalcmdb/cognitive/health_scorer.py
src/internalcmdb/collectors/agent/collectors/certificate_state.py
src/internalcmdb/collectors/agent/collectors/container_resources.py
src/internalcmdb/collectors/agent/collectors/disk_state.py
src/internalcmdb/collectors/agent/collectors/full_hardware.py
src/internalcmdb/collectors/agent/collectors/network_state.py
src/internalcmdb/collectors/agent/collectors/process_inventory.py
src/internalcmdb/collectors/agent/collectors/security_posture.py
src/internalcmdb/collectors/agent/collectors/service_health.py
src/internalcmdb/collectors/agent/collectors/systemd_state.py
src/internalcmdb/collectors/agent/collectors/trust_surface_lite.py
src/internalcmdb/collectors/fleet_health.py
src/internalcmdb/governance/ai_compliance.py
src/internalcmdb/llm/client.py
src/internalcmdb/llm/confidence.py
src/internalcmdb/loaders/ssh_audit_loader.py
src/internalcmdb/motor/playbooks.py
src/internalcmdb/nervous/event_bus.py
src/internalcmdb/observability/logging.py
src/internalcmdb/workers/cognitive_tasks.py
```

**Notă:** Python 3.14's `ast.parse()` parseaza aceste fișiere fără erori (verificat în audit). Semgrep raportează erori de parsing pe 6 din ele din aceeași cauză de compatibilitate de versiune.

### Rezolvare

**Opțiunea 1 (recomandată pe termen scurt):** Rularea bandit prin Python 3.14 explicit, dacă este disponibil:

```bash
python3.14 -m bandit -r src/ -f screen
```

**Opțiunea 2:** Izolarea analizei bandit într-un virtual environment cu Python 3.13 și verificarea că sintaxa 3.14 este compatibilă. Dacă fișierele conțin sintaxă strict 3.14 (ex: PEP 749 annotations), rularea bandit va continua să eșueze până la actualizarea bandit.

**Opțiunea 3 (termen lung):** Înlocuirea bandit cu un tool care nu depinde de versiunea Python pentru parsing. Semgrep (deja instalat) acoperă aceleași categorii de vulnerabilități (B603→subprocess, B608→sql injection) și parsează fișierele corect prin propriul parser.

**Urmărire recomandată:** adăugarea unui assert în CI care eșuează dacă numărul de fișiere skipped de bandit crește față de 22:

```bash
bandit -r src/ -f json 2>&1 | python3 -c "
import sys, json; d=json.load(sys.stdin)
skipped = len(d.get('skipped', []))
print(f'Bandit skipped: {skipped} files')
if skipped > 22: sys.exit(1)
"
```

---

## 7. REAL — Mypy și pip-audit indisponibile în mediul de CI curent

### Problema

Ambele tooluri sunt definite ca dependențe de development în `pyproject.toml`:

```toml
[project.optional-dependencies]
dev = [
  "mypy>=1.17.1",
  "pip-audit>=2.9.0",
  ...
]
```

Dar nu sunt instalate în Python-ul de sistem (`/usr/local/bin/python3`) unde rulează CI-ul:

```
/usr/local/bin/python3: No module named mypy
pip-audit: error: ... requires venv (python3-venv package missing)
```

### Consecință directă

- **Mypy**: zero verificare de tipuri pe 32.000+ linii de cod Python tipat static. Erorile de tip pot ajunge în producție nedetectate.
- **pip-audit**: zero verificare de CVE-uri pe dependențe. Dacă o dependență are o vulnerabilitate publicată (ex: în PyPA Advisory Database), nu există avertizare.

### Rezolvare

**Pentru mypy:**

```bash
# Instalare în venv dedicat
python3 -m venv /opt/mypy-venv
/opt/mypy-venv/bin/pip install mypy types-PyYAML types-requests
/opt/mypy-venv/bin/mypy src/ --ignore-missing-imports
```

Sau adăugarea în `.github/workflows/ci.yml` ca step separat:

```yaml
- name: Type check (mypy)
  run: |
    pip install mypy types-PyYAML types-requests types-setuptools
    mypy src/ --ignore-missing-imports --strict
```

**Pentru pip-audit:**

```bash
apt install python3.13-venv   # sau echivalentul pentru Python activ
pip-audit .
```

Sau în CI:

```yaml
- name: Dependency audit (pip-audit)
  run: |
    pip install pip-audit
    pip-audit --desc on
```

---

## 8. FALSE POSITIVE — tarfile path traversal în updater.py

### Sursă alertă

Semgrep: `tarfile-extractall-traversal` @ `src/internalcmdb/collectors/agent/updater.py:208`

### Analiza codului

```python
# updater.py:207–210
_AGENT_DIR.mkdir(parents=True, exist_ok=True)
with tarfile.open(archive_path, "r:gz") as tar:
    tar.extractall(path=_AGENT_DIR, filter="data")   # linia 209
logger.info("Extracted update to %s", _AGENT_DIR)
```

**`filter="data"` este deja aplicat.** Parametrul `filter="data"` introdus în Python 3.12 (PEP 706) refuză explicit:
- căi absolute
- căi care traversează directoare (`../`)
- fișiere cu permisiuni speciale (setuid, device files)

Semgrep a flagat linia 208 (`with tarfile.open(...)`) fără să detecteze că `filter="data"` este transmis la `extractall()` pe linia imediat următoare. Aceasta este o limitare a analizei statice a semgrep pe expresii multi-linie.

### Concluzie

**Nu necesită nicio modificare.** Fix-ul este deja în cod. Alertă de ignorat.

---

## 9. FALSE POSITIVE — XSS în rate_limit.py

### Sursă alertă

Semgrep: `directly-returned-format-string` (CWE-79) @ `src/internalcmdb/api/middleware/rate_limit.py:44`

### Analiza codului

```python
# rate_limit.py:117–137
def rate_limit_exceeded_handler(_request: Request, exc: RateLimitExceeded) -> Response:
    ...
    return Response(
        content=f'{{"detail": "Rate limit exceeded: {exc.detail}"}}',
        status_code=429,
        media_type="application/json",       # ← JSON, nu HTML
        headers={"Retry-After": retry_after},
    )
```

Regula semgrep `directly-returned-format-string` este concepută pentru **Flask** (`flask.Response` cu `mimetype` implicit `text/html`). Codul folosește **FastAPI/Starlette** `Response` cu `media_type="application/json"`.

`exc.detail` vine din slowapi's `RateLimitExceeded`, construit din șiruri de configurare ale rate limiter-ului (ex: `"10 per 1 minute"`) — nu din input utilizator.

Browsere moderne nu execută JavaScript din răspunsuri JSON. XSS via `application/json` necesită un context de vulnerabilitate separat (ex: un client care reflectă răspunsul în HTML fără escape), nu o vulnerabilitate în această funcție.

### Concluzie

**Nu necesită modificare.** Alertă de ignorat. Dacă se dorește suprimarea alertei:

```python
content=json.dumps({"detail": f"Rate limit exceeded: {exc.detail}"}),
```

Aceasta ar fi o îmbunătățire stilistică (garantează JSON valid independent de caracterele din `exc.detail`) dar nu o necesitate de securitate.

---

## 10. FALSE POSITIVE — Credential disclosure în logs (majority)

### Sursă alertă

Semgrep: `python-logger-credential-disclosure` (CWE-532) — 10 ocurențe

### Analiza fiecărui loc

#### `auth/revocation.py:46, 52` — RISC MINOR (tratat la punctul 3)
JTI-urile sunt logate. Aceasta este singura ocurență cu risc real, acoperit la Problema 3.

#### `config/secrets.py:113`
```python
logger.warning("Secret '%s' not found in Vault or environment", key)
```
`key` este **numele** secretului (ex: `"JWT_SECRET"`), nu valoarea lui. A loga că un cheie nu există este comportament corect de debugging. Nu este o divulgare de credențiale.

#### `llm/budget.py:193`
```python
logger.warning(
    "TOKEN SPIKE detected for %s: current=%d avg=%.0f (%.1fx)",
    caller, current_tokens, avg, current_tokens / avg,
)
```
`caller` este un identificator intern al consumatorului (ex: `"cognitive_query"`). `current_tokens`, `avg` sunt numere întregi reprezentând consum de tokeni. Nu conțin credențiale.

#### `llm/client.py:474`
```python
logger.info("Tokenize request → %s", url)
```
`url` este URL-ul endpoint-ului de tokenizare (ex: `"http://llm-internal:8080/tokenize"`). Este un URL de configurare, nu conține token-uri de autentificare în path sau query string.

#### `llm/security.py:212`
```python
logger.warning(
    "Token budget exceeded for %s: %d + %d > %d",
    caller, entry["used"], tokens_requested, budget_limit,
)
```
Identic cu budget.py: date operaționale, fără credențiale.

### Concluzie

9 din 10 ocurențe sunt false positives generate de regula heuristică a semgrep care detectează cuvintele `token`, `secret` în apropierea apelurilor de logging, fără să analizeze **valorile** logate. Singura ocurență cu risc real este `revocation.py`, tratată la Problema 3.

---

## 11. FALSE POSITIVE — 130× avoid-sqlalchemy-text în migrations/

### Sursă alertă

Semgrep: `avoid-sqlalchemy-text` (CWE-89) — 130 ocurențe, dintre care ~125 în `src/internalcmdb/migrations/versions/`

### Analiza contextului

Migrările Alembic **trebuie** să folosească `sqlalchemy.text()` pentru DDL. Nu există alternativă — SQLAlchemy ORM nu poate exprima `CREATE TABLE ... PARTITION BY RANGE`, `CREATE INDEX CONCURRENTLY`, `CREATE EXTENSION`, `CREATE SCHEMA`, `DO $$ ... $$` blocks și alte construcții PostgreSQL-specifice prin API-ul de expresii tipate.

```python
# exemplu tipic din migrations/versions/0007_hitl_and_telemetry_schema.py
op.execute(sa.text(
    "CREATE TABLE IF NOT EXISTS governance.hitl_item (...)"
))
```

Regula semgrep `avoid-sqlalchemy-text` este concepută pentru **queries runtime** unde `text()` poate ascunde SQL injection. În fișiere de migrare DDL care nu primesc input utilizator, regula nu se aplică.

### Ocurențe runtime care merită atenție (nu false positives)

Semgrep a flagat și locuri din codul runtime, acoperite la Problema 12:
- `src/internalcmdb/api/routers/debug.py:165, 199, 245`
- `src/internalcmdb/api/routers/settings.py:764`
- `src/internalcmdb/cognitive/accuracy_tracker.py:259, 367`
- `src/internalcmdb/cognitive/feedback_loop.py:183, 212`

### Concluzie pentru migrări

125 de alerte din migrations/ sunt false positives structurale. Dacă se dorește suprimarea lor în semgrep:

```yaml
# .semgrep-ignore sau inline:
# nosemgrep: avoid-sqlalchemy-text
```

---

## 12. FALSE POSITIVE — SQL concatenare în debug.py, settings.py, cognitive/

### Sursă alertă

Bandit B608 + Semgrep `avoid-sqlalchemy-text` pe fișiere runtime.

### Analiza per fișier

#### `src/internalcmdb/api/routers/debug.py:158–167`

```python
filters = ["event_type = 'llm_call'"]   # ← string literal
params: dict[str, Any] = {"lim": limit}

if model:
    filters.append("action LIKE '%' || :model || '%'")  # ← string literal + :param
    params["model"] = model                              # ← valoarea merge în params
if status:
    filters.append("status = :status")                  # ← string literal + :param
    params["status"] = status
...
where = " AND ".join(filters)   # ← join de string-uri literale
sql = "... WHERE " + where + _ORDER_LIMIT_CLAUSE
result = await session.execute(text(sql), params)       # ← params legat separat
```

**Evaluare:** `where` este construit exclusiv din string-uri literale definite de developer. Valorile utilizatorului (`model`, `status`, `since`) merg **numai** în `params` dict, niciodată în textul SQL. Pattern-ul este corect din perspectiva SQL injection.

#### `src/internalcmdb/api/routers/settings.py:758–765`

```python
updates = []
if body.target_url is not None:
    updates.append("target_url = :url")    # ← literal
    params["url"] = body.target_url        # ← valoare în params
...
sql = "UPDATE config.notification_channel SET " + ", ".join(updates) + " WHERE ..."
result = await session.execute(text(sql), params)
```

**Evaluare:** `updates` conține exclusiv string-uri literale definite de developer. Valorile request-ului merg în `params`. Pattern corect.

#### `src/internalcmdb/cognitive/accuracy_tracker.py:257–259`

```python
sql = _HITL_FEEDBACK_METRICS_SQL.format(where_clause=where_clause)
result = await self._session.execute(text(sql), params)
```

`_HITL_FEEDBACK_METRICS_SQL` este un template string definit la nivel de modul (linia 33). `where_clause` este construit de `_hitl_feedback_where_clause()` (linia 79–111) care returnează exclusiv string-uri literale cu `:param` placeholders — niciodată valori brute ale utilizatorului. Pattern corect.

#### `src/internalcmdb/cognitive/feedback_loop.py:183–217`

```python
model_filter = ""
if model:
    model_filter = "AND prompt_template_id::text = :model"   # ← literal cu :param
    params["model"] = model                                  # ← valoare în params
result = await self._session.execute(
    text("... WHERE 1=1 " + model_filter),
    params,
)
```

**Evaluare:** `model_filter` este ori `""` ori un string literal cu placeholder. Pattern corect.

### Concluzie

Toate aceste pattern-uri sunt sigure din perspectiva SQL injection. Alertele bandit/semgrep sunt false positives generate de incapacitatea analizei statice de a urmări că valorile utilizatorului ajung în `params`, nu în textul SQL.

**Notă de calitate a codului (fără legătură cu securitatea):** Construcția dinamică a SQL-ului prin concatenare de fragmente statice este mai greu de citit și de întreținut față de ORM. Pe termen lung, refactorizarea spre `sqlalchemy.select()` cu `.where()` chaining ar elimina aceste false positives și ar îmbunătăți lizibilitatea.

---

## 13. INFORMATIONAL — try/except/pass intenționate

### Fișiere și contexte

Bandit B110 a flagat 7 locuri cu `try/except/pass`. Fiecare a fost verificat în cod:

| Fișier | Linie | Context | Justificare |
|--------|-------|---------|-------------|
| `api/middleware/audit.py:66` | `except Exception: pass` | Emitere metrici Prometheus după fiecare request | Metricile sunt non-critice; eșecul lor nu trebuie să blocheze răspunsul HTTP |
| `api/middleware/audit.py:137` | `except Exception: pass` | Decodarea cookie-ului JWT pentru identity în audit log | Cookieul poate fi malformat; fall-through intenționat, documentat cu comentariu |
| `api/routers/auth.py:129` | `except Exception: pass` | Revocarea tokenului la logout | Tokenul poate fi deja invalid; cookieul trebuie șters indiferent |
| `api/routers/auth.py:189` | `except Exception: pass` | Revocarea tokenului la schimbare parolă | Același pattern ca logout |
| `api/routers/collectors.py:504` | `except Exception: pass` | Incrementare contor Prometheus la ingest | Metricile sunt non-critice față de logica de ingest |
| `api/routers/realtime.py:174` | `except Exception: pass` | Receive mesaj inițial de configurare WebSocket (timeout 2s) | Comentariu explicit în cod: "asyncio.TimeoutError ⊂ Exception (S5713)" |
| `api/routers/settings.py:150` | `except Exception: pass` | Decodare JWT pentru username în audit | Același pattern ca audit.py:137 |

Toate sunt pattern-uri intenționate cu justificare clară. Singura care a generat o problemă reală (data_quality.py:374) este tratată la Problema 2.

**Recomandare de calitate (opțional, nu urgentă):** auth.py:189 nu are comentariu explicativ, spre deosebire de auth.py:129 care are `# always clear cookie even if token is invalid`. Adăugarea unui comentariu identic la linia 190 ar păstra consistența codului.

---

---

## 4. REAL — SyntaxError în observability/logging.py pe Python ≤ 3.13

### Fișier
- `src/internalcmdb/observability/logging.py:63`

### Descrierea problemei

```python
# logging.py:61–66
try:
    return json.dumps(log_entry, default=str)
except ValueError, TypeError, OverflowError:   # ← PEP 758, Python 3.14 only
    log_entry.pop("extra", None)
    log_entry["_format_error"] = True
    return json.dumps(log_entry, default=str)
```

`except ValueError, TypeError, OverflowError:` (fără paranteze) este sintaxa introdusă de **PEP 758**, acceptată începând cu Python 3.14. Pe orice Python ≤ 3.13, fișierul ridică `SyntaxError: multiple exception types must be parenthesized` la import.

**Aceasta este cauza directă** a celor 22 fișiere skipped de bandit și a 6 parse errors din semgrep: `logging.py` este importat de `audit.py`, care este importat de marea majoritate a modulelor aplicației. Bandit și semgrep rulează intern cu un parser Python 3.13, deci întâlnesc `SyntaxError` la import chaining.

### Consecință confirmată prin teste

```
ERROR collecting tests/internalcmdb/api/middleware/test_audit.py
    from internalcmdb.api.middleware.audit import ...
    from internalcmdb.observability.logging import set_correlation_id
SyntaxError: multiple exception types must be parenthesized
```

42 din 87 fișiere de test nu pot fi colectate din cauza acestui import chain.

### Evaluare

Dacă proiectul este **exclusiv** destinat Python 3.14+, sintaxa este corectă și toolurile (bandit, semgrep) trebuie actualizate. Dacă există vreun context unde se rulează pe Python 3.13 (ex: CI folosește `python-version: ["3.14"]` în `matrix` — corect), atunci nu există o problemă de rulare în producție.

**Problema reală rămâne**: bandit și semgrep nu pot analiza aceste fișiere deloc — blind spot de securitate confirmat.

### Rezolvare — compatibilitate tooluri, nu producție

Adăugarea parantezelor rezolvă compatibilitatea cu toate toolurile de analiză, fără să schimbe comportamentul pe Python 3.14:

```python
try:
    return json.dumps(log_entry, default=str)
except (ValueError, TypeError, OverflowError):   # compatibil 3.10+
    log_entry.pop("extra", None)
    log_entry["_format_error"] = True
    return json.dumps(log_entry, default=str)
```

Același pattern trebuie aplicat în toate celelalte fișiere care folosesc PEP 758 syntax, dacă scopul este ca bandit/semgrep să le poată analiza.

---

## 8. REAL — kpi-card.tsx: acces și mutare ref în timpul render-ului

### Fișier
- `frontend/src/components/dashboard/kpi-card.tsx:31–32, 47`

### Descrierea problemei

ESLint `react-hooks/refs` raportează 9 erori pe același component:

```tsx
// kpi-card.tsx:29–32
const prevRef = useRef<number | undefined>(undefined);
const isNew = dataUpdatedAt !== undefined
           && dataUpdatedAt !== prevRef.current      // ← citire ref în render
           && prevRef.current !== undefined;         // ← citire ref în render (din nou)
prevRef.current = dataUpdatedAt;                     // ← scriere ref în render

// linia 47 — isNew folosit în JSX (derivat din ref, în render)
className={cn("kpi-v", isNew && "kpi-v-flash")}
```

### De ce e o problemă reală

React's Strict Mode (și React 19) rulează componentele de două ori în development pentru a detecta efectele secundare. Citirea și scrierea unui ref în corpul funcției de render este un efect secundar — valoarea `prevRef.current` poate diferi între cele două rulări, producând comportament nedeterministic. Regula `react-hooks/refs` din `eslint-plugin-react-hooks` (v5+) interzice explicit acest pattern.

În practică: animația "flash la update" poate să nu se declanșeze sau să se declanșeze dublu în Strict Mode.

### Rezolvare

Mutarea logicii de comparare și scriere a ref-ului într-un `useEffect`, și stocarea stării `isNew` în state React:

```tsx
import { useEffect, useRef, useState } from "react";

export function KpiCard({ dataUpdatedAt, ... }: KpiCardProps) {
  const prevRef = useRef<number | undefined>(undefined);
  const [isNew, setIsNew] = useState(false);

  useEffect(() => {
    if (
      dataUpdatedAt !== undefined &&
      prevRef.current !== undefined &&
      dataUpdatedAt !== prevRef.current
    ) {
      setIsNew(true);
      const timer = setTimeout(() => setIsNew(false), 600); // durata animației CSS
      return () => clearTimeout(timer);
    }
    prevRef.current = dataUpdatedAt;
  }, [dataUpdatedAt]);

  return (
    <div className={cn("kpi", className)}>
      ...
      <div
        key={dataUpdatedAt}
        className={cn("kpi-v", isNew && "kpi-v-flash")}
      >
        {value}
      </div>
      ...
    </div>
  );
}
```

Alternativ, dacă animația este implementată pur CSS cu `key={dataUpdatedAt}` (re-mount la schimbare), `isNew` și `prevRef` pot fi eliminate complet — `key` schimbat forțează deja re-mount-ul care declanșează animația CSS de intrare.

---

## 9. REAL — 7 paneluri Settings: setState apelat sincron în useEffect

### Fișiere
- `frontend/src/app/settings/panels/GuardPanel.tsx:35`
- `frontend/src/app/settings/panels/HITLPanel.tsx:67`
- `frontend/src/app/settings/panels/LLMPanel.tsx:85`
- `frontend/src/app/settings/panels/ObservabilityPanel.tsx:40`
- `frontend/src/app/settings/panels/RetentionPanel.tsx:34`
- `frontend/src/app/settings/panels/SelfHealPanel.tsx:30`
- `frontend/src/app/settings/panels/TokenBudgetPanel.tsx:35`

### Descrierea problemei

Pattern identic în toate 7 paneluri (exemplu din GuardPanel.tsx):

```tsx
const [form, setForm] = useState<FormState | null>(null);
const { data } = useQuery<GuardConfig>({ queryKey: ["settings", "guard"], ... });

useEffect(() => {
  if (data && !form) setForm({ fail_closed: data.fail_closed, timeout_s: data.timeout_s });
}, [data, form]);   // ← setState în corpul effect-ului, nu într-un callback
```

ESLint `react-hooks/set-state-in-effect` flaghează apelul `setForm(...)` în corpul direct al `useEffect`. Pattern-ul produce un render suplimentar: mai întâi componenta se renderează cu `form = null`, useEffect rulează și setează form, ceea ce declanșează al doilea render.

### De ce e o problemă reală

1. **Render cascadat**: fiecare mount produce 2 render-uri în loc de 1.
2. **Anti-pattern documentat de React**: React recomandă inițializarea state-ului direct, nu printr-un effect.
3. **Risc de buclă**: dacă `form` este inclus în deps array, există un potențial de re-triggering (aici mitigat de `!form`).

### Rezolvare

Inițializarea `form` direct cu valoarea din `data` folosind `useState` lazy initializer sau derivând state-ul din query fără a-l copia:

**Opțiunea 1 — eliminare `form` state, scriere directă în query cache:**

```tsx
// GuardPanel.tsx — variantă simplificată
const queryClient = useQueryClient();
const { data, isLoading } = useQuery<GuardConfig>({
  queryKey: ["settings", "guard"],
  queryFn: getGuardConfig,
  staleTime: 30_000,
});

// form state derivat direct din data, cu override local până la save
const [localOverrides, setLocalOverrides] = useState<Partial<GuardConfig>>({});
const form = data ? { ...data, ...localOverrides } : null;
```

**Opțiunea 2 — `useEffect` care nu apelează setState în corp, ci prin derivare:**

```tsx
// Înlocuiește pattern-ul useEffect/setForm cu useMemo
const form = useMemo<FormState | null>(
  () => data ? { fail_closed: data.fail_closed, timeout_s: data.timeout_s } : null,
  [data]
);
```

Aceasta elimină complet `form` state și `useEffect`, reducând render-urile la 1 per fetch.

---

## 10. REAL — useWebSocket.ts: auto-referință ilegală și dependency lipsă

### Fișier
- `frontend/src/lib/useWebSocket.ts:132, 138`

### Eroare 1: auto-referință (`react-hooks/immutability`)

```ts
// useWebSocket.ts:132
reconnectTimerRef.current = setTimeout(connect, delay);
//                                      ^^^^^^^ linia 132, col 46
// ESLint: "Cannot access variable before it is declared"
```

`connect` este definit prin `useCallback` care începe la linia 67. Linia 132 este în interiorul callback-ului `connect` însuși — `connect` se referă la el însuși prin `setTimeout`. În momentul execuției JavaScript, closure-ul captează referința la `connect` după ce declarația este completă, deci **funcțional codrul este corect**. ESLint's `react-hooks/immutability` (v5) flaghează totuși pattern-ul deoarece `connect` nu poate fi garantat stabil referențial la momentul capturării (depinde de deps array-ul `useCallback`).

**Consecință practică**: dacă oricare din dependențele `useCallback` (url, enabled, onMessage etc.) se schimbă, se creează o nouă referință `connect`, dar timer-ul anterior poate încă ține referința la vechiul `connect`. Aceasta poate produce reconnect-uri cu configurație depășită.

### Eroare 2: dependency lipsă (`react-hooks/exhaustive-deps`)

```ts
// useWebSocket.ts:138
}, [url, enabled, onMessage, onOpen, onClose, heartbeatIntervalMs, clearTimers]);
// ^^^ lipsește: maxRetries
```

`maxRetries` este folosit la linia 124 (`if (retryCountRef.current >= maxRetries)`) dar nu apare în deps array. Dacă `maxRetries` se schimbă după mount, `connect` va folosi valoarea veche captată la primul render.

### Rezolvare

Stocarea `maxRetries` într-un ref pentru a-l accesa mereu la zi fără să fie dependency:

```ts
// useWebSocket.ts — adăugat după celelalte refs
const maxRetriesRef = useRef(maxRetries);
useEffect(() => { maxRetriesRef.current = maxRetries; }, [maxRetries]);

// linia 124 — schimbat
if (retryCountRef.current >= maxRetriesRef.current) {
```

Pentru auto-referința `connect`, soluția este un ref care ține ultima versiune a funcției:

```ts
const connectRef = useRef<() => void>(() => {});
const connect = useCallback(() => {
  // ... tot corpul
  reconnectTimerRef.current = setTimeout(() => connectRef.current(), delay); // indirect
}, [url, enabled, onMessage, onOpen, onClose, heartbeatIntervalMs, clearTimers]);
useEffect(() => { connectRef.current = connect; }, [connect]);
```

---

## 11. REAL — hooks.ts: Date.now() apelat în timpul render-ului

### Fișier
- `frontend/src/lib/hooks.ts:23`

### Descrierea problemei

```ts
// hooks.ts:21–23
const nextAt = dataUpdatedAt ? dataUpdatedAt + intervalMs : null;
const remainingMs = nextAt ? Math.max(0, nextAt - Date.now()) : intervalMs;
//                                                 ^^^^^^^^^^ apel impure în render
```

`Date.now()` este o funcție impură — returnează valori diferite la fiecare apel. Apelată în corpul unui hook (care rulează în timpul render-ului), produce valori diferite între cele două rulări din Strict Mode, încălcând regula React că componentele și hook-urile trebuie să fie idempotente.

### Context suplimentar

Hook-ul `useCountdown` are deja un `useEffect` cu `setInterval` care incrementează un counter `tick` pentru a forța re-render la fiecare secundă. `Date.now()` în render este intenționat (calculează cât timp a mai rămas), dar regula `react-hooks/impure` îl flaghează.

### Rezolvare

Capturarea timpului curent în state, actualizat prin interval (deja existent):

```ts
// hooks.ts — modificat
export function useCountdown({ dataUpdatedAt, intervalMs }: CountdownOpts) {
  const [now, setNow] = useState(() => Date.now()); // valoare inițială o singură dată

  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, []);

  const lastRefreshed = dataUpdatedAt ? new Date(dataUpdatedAt) : null;
  const nextAt = dataUpdatedAt ? dataUpdatedAt + intervalMs : null;
  const remainingMs = nextAt ? Math.max(0, nextAt - now) : intervalMs; // 'now' din state
  const secsLeft = Math.ceil(remainingMs / 1000);
  const progress = Math.min(1, Math.max(0, remainingMs / intervalMs));

  return { secsLeft, progress, lastRefreshed };
}
```

Aceasta elimină apelul `Date.now()` din render și îl mută în effect — `now` devine state stabil în timpul unui render individual.

---

## 12. REAL — 2 variabile importate/declarate dar neutilizate în production code

### Fișiere
- `frontend/src/components/workers/job-table.tsx` — `formatDate` importat, neutilizat
- `frontend/src/app/documents/page.tsx` — `Card` importat, neutilizat

### Descrierea problemei

```tsx
// job-table.tsx:17
import { formatDate } from "@/lib/hooks";   // ← 'formatDate' neutilizat
```

```tsx
// documents/page.tsx:11
import { Card } from "@/components/ui/card";   // ← 'Card' neutilizat în componentă
```

Importuri neutilizate măresc bundle-ul (tree-shaking-ul nu garantează eliminarea în toate cazurile), introduc dependențe artificiale la module, și poluează IntelliSense.

### Rezolvare

Ștergerea importurilor nefolosite:

```tsx
// job-table.tsx — linia 17 se elimină complet
// documents/page.tsx — linia 11 se elimină complet (sau Card se prefixează cu _ dacă e rezervat)
```

---

## 13. REAL — 17 componente fără displayName în fișiere de test

### Fișiere
Toate 17 fișierele `src/__tests__/**/*.test.tsx`.

### Descrierea problemei

```tsx
// exemplu din audit-page.test.tsx:10
const MockRouter = ({ children }: { children: React.ReactNode }) => (
  <div>{children}</div>
);
// ESLint react/display-name: "Component definition is missing display name"
```

Componentele anonime definite ca arrow functions în fișierele de test nu au `displayName` setat. ESLint `react/display-name` raportează eroare.

### Evaluare

Problemă de calitate a codului de test, nu de producție. Nu afectează funcționalitatea sau bundle-ul final. Dar dacă `pnpm run lint` eșuează în CI din cauza acestor erori (ceea ce se întâmplă), blochează nemeritat pipeline-ul.

### Rezolvare — două opțiuni

**Opțiunea 1 — adăugare displayName manual (corectă semantic):**

```tsx
const MockRouter = ({ children }: { children: React.ReactNode }) => (
  <div>{children}</div>
);
MockRouter.displayName = "MockRouter";
```

**Opțiunea 2 — dezactivare regulă în fișierele de test (pragmatică):**

Adăugarea în `.eslintrc` (sau `eslint.config.mjs`):

```js
{
  files: ["src/__tests__/**/*.test.tsx"],
  rules: {
    "react/display-name": "off"
  }
}
```

Opțiunea 2 este mai pragmatică: regula `react/display-name` este relevantă în producție (pentru debugging în React DevTools), nu în mock-urile din teste.

---

## 14. REAL — --forwarded-allow-ips "*" în Dockerfile.api

### Fișier
- `Dockerfile.api:55–56`

### Descrierea problemei

```dockerfile
CMD ["uvicorn", "internalcmdb.api.main:app",
     "--host", "0.0.0.0",
     "--port", "4444",
     "--workers", "2",
     "--proxy-headers",
     "--forwarded-allow-ips", "*"]    # ← trust all IPs
```

`--forwarded-allow-ips "*"` spune lui uvicorn să accepte header-ele `X-Forwarded-For`, `X-Forwarded-Proto` și `X-Real-IP` de la **orice sursă**, indiferent de IP. Aceasta înseamnă că orice client care ajunge direct la portul 4444 poate seta `X-Forwarded-For: 127.0.0.1` și apărea ca o cerere locală sau poate falsifica IP-ul aparent.

### Impact în contextul acestui proiect

Rate limiter-ul (`rate_limit.py`) folosește `X-Forwarded-For` pentru a deriva cheia de limitare:

```python
# rate_limit.py:45–47
forwarded = request.headers.get("x-forwarded-for")
if forwarded:
    return forwarded.split(",")[0].strip()
```

Un atacator care accesează direct portul 4444 (dacă nu este protejat de firewall) poate rota `X-Forwarded-For` pentru a eluda rate limiting-ul.

Soluția corectă este să specifici IP-ul real al proxy-ului (Traefik/nginx):

```dockerfile
CMD ["uvicorn", "internalcmdb.api.main:app",
     "--host", "0.0.0.0",
     "--port", "4444",
     "--workers", "2",
     "--proxy-headers",
     "--forwarded-allow-ips", "127.0.0.1,10.0.0.0/8"]  # doar rețeaua internă
```

Sau, dacă IP-ul proxy-ului este variabil, configurarea printr-o variabilă de mediu:

```dockerfile
CMD ["sh", "-c", "uvicorn internalcmdb.api.main:app \
     --host 0.0.0.0 --port 4444 --workers 2 \
     --proxy-headers \
     --forwarded-allow-ips ${TRUSTED_PROXY_IPS:-127.0.0.1}"]
```

---

## 15. REAL — Node.js 25 în Dockerfile vs Node.js 22 în CI

### Fișiere
- `Dockerfile.frontend:4` — `ARG NODE_VERSION=25.8.1`
- `.github/workflows/ci.yml:91` — `node-version: "22"`

### Descrierea problemei

Aplicația frontend se construiește cu **Node.js 25.8.1** în Dockerfile (imaginea de producție), dar CI-ul rulează testele și lint-ul pe **Node.js 22**. Node.js 25 este o versiune "Current" (nesuportată LTS), iar Node.js 22 este LTS activ (Jod).

Discrepanța înseamnă că:
1. Testele trec pe Node 22 dar imaginea de producție rulează pe Node 25 — comportamente diferite ale V8, module resolution, etc.
2. pnpm@10.32.1 din Dockerfile poate să nu fie compatibil identic cu versiunea folosită de `pnpm/action-setup@v4` în CI (fără version pin).
3. Node 25 are o durată de suport scurtă — va deveni EOL rapid.

### Rezolvare

Alinierea versiunilor la **Node.js 22 LTS** (suport până în Aprilie 2027) în ambele locuri:

```dockerfile
# Dockerfile.frontend
ARG NODE_VERSION=22.14.0
```

```yaml
# ci.yml
- uses: actions/setup-node@v4
  with:
    node-version: "22"
```

Și alinierea versiunii pnpm:

```yaml
# ci.yml
- uses: pnpm/action-setup@v4
  with:
    version: "10.32.1"   # ← pin explicit, identic cu Dockerfile
```

---

## 16. REAL — Semgrep community scan nu blochează CI la findings

### Fișier
- `.github/workflows/ci.yml:133–150`

### Descrierea problemei

```yaml
- name: Run community rulesets (requires SEMGREP_APP_TOKEN secret)
  run: |
    semgrep scan \
            --config p/python \
            ...
            --severity WARNING \
            --error \                           # ← exit code non-zero la findings
            --json \
            src frontend/src > semgrep-community.json 2>&1   # ← redirect captează exit code!
```

`--error` face semgrep să returneze exit code 1 când găsește findings. Dar `> semgrep-community.json 2>&1` redirectează **atât stdout cât și stderr** către fișier — bash evaluează exit code-ul ultimei comenzi (`>`), care este întotdeauna 0 (redirectarea reușește).

Rezultatul: **pasul de CI nu eșuează niciodată**, indiferent de câte findings găsește semgrep. Output-ul JSON este salvat, dar CI-ul nu îl verifică.

### Verificare

În bash: `command > file 2>&1` — exit code-ul pipes/redirectărilor nu propagă exit code-ul comenzii originale. `echo $?` după aceasta returnează 0.

### Rezolvare

Salvarea output-ului fără a suprima exit code-ul:

```yaml
- name: Run community rulesets
  run: |
    set -o pipefail
    semgrep scan \
            --config p/python \
            --config p/owasp-top-ten \
            --config p/fastapi \
            --config p/typescript \
            --config p/react \
            --config p/sql-injection \
            --config p/xss \
            --config p/secrets \
            --severity WARNING \
            --error \
            --json \
            src frontend/src | tee semgrep-community.json
```

`tee` scrie la fișier și la stdout simultan; `set -o pipefail` propagă exit code-ul semgrep prin pipe. Alternativ:

```yaml
run: |
  semgrep scan ... --json --output semgrep-community.json   # --output scrie fișierul
  # exit code-ul semgrep este propagat normal
```

---

## 17. REAL — Test suite nu poate rula în mediul curent (42 erori de colecție)

### Descrierea problemei

Rularea `pytest` pe Python 3.13 (unde e instalat) produce **42 erori la colecție** din două cauze:

**Cauza 1 — Sintaxă Python 3.14** (tratată la problema 4):
Fișierele care importă `observability/logging.py` (și prin chain-ul de importuri, marea majoritate a modulelor) nu pot fi parsate de Python 3.13.

**Cauza 2 — Dependențe Python lipsă din mediu**:
```
ModuleNotFoundError: No module named 'arq'
ModuleNotFoundError: No module named 'redis'
ModuleNotFoundError: No module named 'slowapi'
ModuleNotFoundError: No module named 'prometheus_client'
ModuleNotFoundError: No module named 'argon2'
ModuleNotFoundError: No module named 'networkx'
ModuleNotFoundError: No module named 'croniter'
ImportError: email-validator is not installed
```

Dependențele din `pyproject.toml` nu sunt instalate în Python-ul de sistem. Testele sunt concepute să ruleze într-un virtualenv cu `pip install -e ".[dev]"`.

### Rezultat curent

Pe Python 3.13 cu dependențe parțiale: **45 teste trec, 42 fișiere nu se colectează**. Acoperire: **7.26%** față de pragul impus de 55%.

Pe Python 3.14 (mediul corect) cu toate dependențele instalate via `pip install -e ".[dev]"`, testele ar trebui să colecteze corect.

### Rezolvare

Crearea unui virtualenv dedicat cu Python 3.14 și instalarea completă a dependențelor:

```bash
python3.14 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest tests/ -q
```

În CI, pasul `Install dependencies` din `ci.yml` face deja `pip install -e ".[dev]"` pe Python 3.14 — deci în CI testele ar trebui să ruleze corect. Problema apare doar în mediul local de pe server unde lipsesc venv și dependențele.

---

## 18. REAL — Erori structurale YAML în fișiere deploy/

### 18a. `deploy/orchestrator/docker-compose.postgresql.yml:23–26`

**Problema:** yamllint raportează `too many spaces after colon` pe liniile cu variabilele de environment:

```yaml
environment:
  POSTGRES_DB:       ${POSTGRES_DB:-internalCMDB}   # ← 7 spații extra
  POSTGRES_USER:     ${POSTGRES_USER:-internalcmdb} # ← 5 spații extra
  POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
  PGDATA:            /var/lib/postgresql/data/pgdata # ← 12 spații extra
```

Standardul YAML (și yamllint cu regula `colons`) impune exact un spațiu după `:`.

**Rezolvare:**

```yaml
environment:
  POSTGRES_DB: ${POSTGRES_DB:-internalCMDB}
  POSTGRES_USER: ${POSTGRES_USER:-internalcmdb}
  POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
  PGDATA: /var/lib/postgresql/data/pgdata
```

### 18b. `deploy/wapp-pro-app/docker-compose.yml:25, 51, 75, 96`

**Problema:** yamllint raportează `too many spaces inside braces` pe liniile cu opțiunile de logging:

```yaml
options: { max-size: "20m", max-file: "5" }
#        ^                               ^
```

**Rezolvare — block mapping:**

```yaml
options:
  max-size: "20m"
  max-file: "5"
```

---

## 19. FALSE POSITIVE — tarfile path traversal în updater.py

### Sursă alertă

Semgrep: `tarfile-extractall-traversal` (CWE-22) @ `src/internalcmdb/collectors/agent/updater.py:208`

### Analiza codului

```python
# updater.py:207–210
with tarfile.open(archive_path, "r:gz") as tar:
    tar.extractall(path=_AGENT_DIR, filter="data")   # fix deja prezent pe linia 209
```

`filter="data"` (Python 3.12+ / PEP 706) blochează explicit căi absolute și traversări `../`. Semgrep a flagat linia 208 fără să detecteze parametrul de pe linia 209.

**Concluzie:** fix deja în cod, alertă de ignorat.

---

## 20. FALSE POSITIVE — XSS în rate_limit.py

### Sursă alertă

Semgrep: `directly-returned-format-string` (CWE-79) @ `src/internalcmdb/api/middleware/rate_limit.py:44`

### Analiza codului

```python
return Response(
    content=f'{{"detail": "Rate limit exceeded: {exc.detail}"}}',
    status_code=429,
    media_type="application/json",       # ← JSON, nu HTML
    ...
)
```

Regula este concepută pentru Flask cu `text/html`. Codul folosește FastAPI cu `application/json`. `exc.detail` vine din slowapi, nu din input utilizator. Alertă de ignorat.

---

## 21. FALSE POSITIVE — Credential disclosure în logs (majority)

Semgrep `python-logger-credential-disclosure` — 10 ocurențe, din care:

- `config/secrets.py:113` — loghează **numele** cheii absente, nu valoarea
- `llm/budget.py:193` — loghează contori de tokeni (numere întregi)
- `llm/client.py:474` — loghează URL-ul endpoint-ului intern
- `llm/security.py:212` — loghează contori de buget
- `auth/revocation.py:46,52,62,68` — loghează JTI (tratat la Problema 3)

Regula heuristică detectează cuvintele `token`, `secret` lângă apeluri de logging, fără să analizeze valorile. 8 din 10 sunt false positives.

---

## 22. FALSE POSITIVE — 130× avoid-sqlalchemy-text în migrations/

Migrările Alembic **trebuie** să folosească `sa.text()` pentru DDL PostgreSQL-specific. Regula se aplică pentru queries runtime, nu DDL. Alertele din `migrations/versions/` sunt false positives structurale.

---

## 23. FALSE POSITIVE — SQL concatenare în debug.py, settings.py, cognitive/

Toate pattern-urile concatenează **literal strings** definite de developer. Valorile utilizatorului merg exclusiv în `params` dict, niciodată în textul SQL. Pattern-ul este sigur — analiza statică nu poate verifica aceasta.

---

## 24. INFORMATIONAL — try/except/pass intenționate

| Fișier | Context | Justificare |
|--------|---------|-------------|
| `api/middleware/audit.py:66` | Metrici Prometheus | Non-critice, nu blochează request-ul |
| `api/middleware/audit.py:137` | Decodare cookie malformat | Fall-through documentat |
| `api/routers/auth.py:129` | Logout cu token invalid | Cookie se șterge indiferent |
| `api/routers/auth.py:189` | Schimbare parolă | Idem, lipsă comentariu explicativ |
| `api/routers/collectors.py:504` | Metrici Prometheus | Non-critice |
| `api/routers/realtime.py:174` | WebSocket timeout config | Documentat cu S5713 |
| `api/routers/settings.py:150` | JWT decode pentru username | Fall-through spre anonymous |

---

## Sumar de prioritizare

| # | Problemă | Prioritate | Efort |
|---|---------|-----------|-------|
| 4 | SyntaxError logging.py — blochează 42 teste și toată analiza bandit/semgrep | **P1** | 2 min (adăugare paranteze) |
| 1 | SQL concatenare fără validare `child` (retention.py) | **P1** | 5 min |
| 2 | Excepție silențioasă data_quality.py | **P1** | 5 min |
| 14 | `--forwarded-allow-ips "*"` în Dockerfile.api | **P1** | 5 min |
| 16 | Semgrep CI nu blochează la findings | **P1** | 10 min |
| 8 | kpi-card.tsx: ref accesat în render | **P2** | 30 min |
| 9 | 7 Settings panels: setState în useEffect | **P2** | 45 min |
| 10 | useWebSocket: auto-referință + dep lipsă | **P2** | 30 min |
| 11 | hooks.ts: Date.now() în render | **P2** | 15 min |
| 3 | JTI logat complet (revocation.py) | **P2** | 10 min |
| 15 | Node.js 25 vs 22, pnpm nepinuit | **P2** | 10 min |
| 17 | Test suite nu rulează în mediul local | **P2** | Configurare venv |
| 12 | 2 importuri neutilizate production code | **P3** | 2 min |
| 13 | 17 display-name lipsă în teste | **P3** | Regula ESLint off în tests |
| 18 | Erori structurale YAML deploy/ | **P3** | 15 min |
| 5 | 44 erori ruff subprojects/ | **P3** | `ruff --fix` |
| 6 | Bandit nu analizează 22 fișiere | **P3** | Rezolvat de P1 \#4 |
| 7 | Mypy și pip-audit indisponibile | **P3** | Configurare CI |
| 19–24 | False positives documentate | — | Suprimare selectivă |
