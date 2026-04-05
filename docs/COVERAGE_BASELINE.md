# Baseline acoperire (pytest + coverage)

- **Python:** gate curent `fail_under=55%` (branch coverage activ) cu `omit` documentat pentru migrări, seeds, colectori agent pe host, loaders, motor, `api/main.py`, worker scheduler/retention/run.
- **Frontend (Vitest):** praguri pe `src/lib/**` (linii ~55%, funcții ~30%) — paginile Next vor crește acoperirea în iterări următoare.
- Rulare locală: `make test`, `cd frontend && pnpm exec vitest run --coverage`.
