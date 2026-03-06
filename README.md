# ProiecteIT - Enterprise Python Baseline

This repository contains a complete enterprise-grade baseline for Python development with strict quality and security controls.

## Standards Implemented

- Python `3.14.x` as default runtime
- `src/` package layout
- Strict static analysis (`ruff`, `mypy`)
- Unit tests with coverage gate (`pytest`, `pytest-cov`)
- SAST and dependency scans (`bandit`, `pip-audit`)
- Pre-commit hooks for local gate enforcement
- GitHub Actions CI for pull requests and pushes

## Quick Start

```bash
./scripts/bootstrap.sh
source .venv/bin/activate
make check
```

## Main Commands

```bash
make lint
make type
make test
make security
make audit
make check
make build
```

## Project Layout

```text
src/proiecteit/       # Application package
tests/                # Unit tests
.github/workflows/    # CI pipelines
scripts/              # Project automation scripts
```

## Enterprise Recommendations

- Enforce branch protection with required checks: `pre-commit`, `CI`
- Require PR reviews and signed commits
- Use dependency update automation (Dependabot/Renovate)
- Store secrets only in a vault or GitHub encrypted secrets
