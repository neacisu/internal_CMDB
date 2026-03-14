PYTHON ?= python

.PHONY: help init install lint format type test test-cov security audit check build clean run \
        api ui worker migrate-worker dev-up dev-down \
        start stop restart status logs

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
	@echo "  start         - Start entire stack (Redis + API + worker + UI)"
	@echo "  stop          - Stop entire stack"
	@echo "  restart       - Restart entire stack"
	@echo "  status        - Show status of all services"
	@echo "  logs          - Tail logs from all services"

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
	pytest --cov=src/proiecteit --cov-report=term-missing --cov-report=xml

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
