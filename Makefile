PYTHON ?= python

.PHONY: help init install lint format type test test-cov security audit check build clean run \
        api ui worker migrate-worker migrate-check dev-up dev-down \
        start stop restart status logs \
        deploy deploy-api deploy-frontend deploy-logs

help:
	@echo "Targets:"
	@echo "  init          - Create venv, install deps, install pre-commit hooks"
	@echo "  install       - Install package + dev dependencies"
	@echo "  lint          - Run Ruff lint checks"
	@echo "  format        - Run Ruff formatter"
	@echo "  type          - Run mypy strict type checks"
	@echo "  test          - Run pytest"
	@echo "  test-cov      - Run pytest with coverage"
	@echo "  security      - Run Bandit on source"
	@echo "  audit         - Run pip-audit for dependencies"
	@echo "  check         - Run all quality gates"
	@echo "  build         - Build wheel and sdist"
	@echo "  run           - Run package entrypoint"
	@echo "  clean         - Remove local artifacts"
	@echo ""
	@echo "  api           - Start FastAPI dev server (uvicorn reload)"
	@echo "  ui            - Start Next.js dev server (Turbopack)"
	@echo "  worker        - Start ARQ worker process"
	@echo "  migrate-worker - Apply migration 0003 (worker schema)"
	@echo "  dev-up        - Start local dev support services (Redis)"
	@echo "  dev-down      - Stop local dev support services"
	@echo ""
	@echo "  start         - Start entire stack (shared Redis check + API + worker + collector agent + UI)"
	@echo "  stop          - Stop entire stack"
	@echo "  restart       - Restart entire stack"
	@echo "  status        - Show status of all services"
	@echo "  logs          - Tail logs from all services"
	@echo ""
	@echo "  deploy        - Push branch + rebuild all images + restart stack on orchestrator"
	@echo "  deploy-api    - Rebuild only API+worker image + restart (faster)"
	@echo "  deploy-frontend - Rebuild only frontend image + restart"
	@echo "  deploy-logs   - Tail live logs from all containers on orchestrator"

init:
	$(PYTHON) -m venv .venv
	. .venv/bin/activate && pip install --upgrade pip
	. .venv/bin/activate && pip install -e ".[dev]"
	. .venv/bin/activate && pre-commit install

install:
	pip install --upgrade pip
	pip install -e ".[dev]"

lint:
	ruff check src tests

format:
	ruff format src tests

type:
	mypy src tests

test:
	pytest

test-cov:
	pytest --cov=src/proiecteit --cov=src/internalcmdb --cov-report=term-missing --cov-report=xml

security:
	bandit -c pyproject.toml -r src

audit:
	pip-audit

check: lint type test security audit

build:
	python -m build

run:
	python -m proiecteit

api:
	uvicorn internalcmdb.api.main:app --reload --host 0.0.0.0 --port 8000

ui:
	cd frontend && pnpm dev

worker:
	arq internalcmdb.workers.queue.WorkerSettings

migrate-worker:
	alembic -c alembic.ini upgrade head

migrate-check:
	@echo "=== Migration dry-run (SQL preview) ==="
	@alembic -c alembic.ini upgrade head --sql > /tmp/migration_preview.sql 2>&1 || true
	@echo "Checking for dangerous operations..."
	@if grep -iE 'DROP\s+(TABLE|COLUMN|INDEX|CONSTRAINT|SCHEMA)|TRUNCATE\s|DELETE\s+FROM|SET\s+\S+\s*=\s*NULL' /tmp/migration_preview.sql 2>/dev/null; then \
		echo "WARNING: Destructive or data-loss operations detected in migration!"; \
		echo "Review /tmp/migration_preview.sql before proceeding."; \
		exit 1; \
	else \
		echo "No destructive operations found."; \
	fi
	@echo "=== Migration check passed ==="

dev-up:
	docker compose -f docker-compose.dev.yml up -d

dev-down:
	docker compose -f docker-compose.dev.yml down

start:
	./stack.sh start

stop:
	./stack.sh stop

restart:
	./stack.sh restart

status:
	./stack.sh status

logs:
	./stack.sh logs

clean:
	rm -rf .venv .mypy_cache .ruff_cache .pytest_cache build dist *.egg-info coverage.xml .coverage

# ── Orchestrator deploy ────────────────────────────────────────────────────────
DEPLOY_DIR   = /opt/stacks/internalcmdb
COMPOSE_FILE = $(DEPLOY_DIR)/deploy/orchestrator/docker-compose.internalcmdb.yml

deploy:
	git push origin work/internal-cmdb-bootstrap
	ssh orchestrator 'cd $(DEPLOY_DIR) && git pull origin work/internal-cmdb-bootstrap'
	ssh orchestrator 'cd $(DEPLOY_DIR) && DOCKER_BUILDKIT=1 docker build -f Dockerfile.api -t ghcr.io/alexneacsu/internalcmdb-api:latest .'
	ssh orchestrator 'cd $(DEPLOY_DIR) && DOCKER_BUILDKIT=1 docker build -f Dockerfile.frontend -t ghcr.io/alexneacsu/internalcmdb-frontend:latest .'
	ssh orchestrator 'docker compose -f $(COMPOSE_FILE) up -d'
	@echo "Deploy complete → https://infraq.app"

deploy-api:
	git push origin work/internal-cmdb-bootstrap
	ssh orchestrator 'cd $(DEPLOY_DIR) && git pull origin work/internal-cmdb-bootstrap'
	ssh orchestrator 'cd $(DEPLOY_DIR) && DOCKER_BUILDKIT=1 docker build -f Dockerfile.api -t ghcr.io/alexneacsu/internalcmdb-api:latest .'
	ssh orchestrator 'docker compose -f $(COMPOSE_FILE) up -d --no-deps internalcmdb-api internalcmdb-worker'
	@echo "API+worker restarted → https://infraq.app/health"

deploy-frontend:
	git push origin work/internal-cmdb-bootstrap
	ssh orchestrator 'cd $(DEPLOY_DIR) && git pull origin work/internal-cmdb-bootstrap'
	ssh orchestrator 'cd $(DEPLOY_DIR) && DOCKER_BUILDKIT=1 docker build -f Dockerfile.frontend -t ghcr.io/alexneacsu/internalcmdb-frontend:latest .'
	ssh orchestrator 'docker compose -f $(COMPOSE_FILE) up -d --no-deps internalcmdb-frontend'
	@echo "Frontend restarted → https://infraq.app"

deploy-logs:
	ssh orchestrator 'docker compose -f $(COMPOSE_FILE) logs -f'

rollback-migration:
	alembic -c alembic.ini downgrade -1
	@echo "Rolled back one migration step"

rollback-api:
	ssh orchestrator 'docker compose -f $(COMPOSE_FILE) up -d --no-deps internalcmdb-api internalcmdb-worker'
	@echo "API + worker restarted with current :latest image"
