PYTHON ?= python

.PHONY: help init install lint format type test test-cov security audit check build clean run

help:
	@echo "Targets:"
	@echo "  init      - Create venv, install deps, install pre-commit hooks"
	@echo "  install   - Install package + dev dependencies"
	@echo "  lint      - Run Ruff lint checks"
	@echo "  format    - Run Ruff formatter"
	@echo "  type      - Run mypy strict type checks"
	@echo "  test      - Run pytest"
	@echo "  test-cov  - Run pytest with coverage"
	@echo "  security  - Run Bandit on source"
	@echo "  audit     - Run pip-audit for dependencies"
	@echo "  check     - Run all quality gates"
	@echo "  build     - Build wheel and sdist"
	@echo "  run       - Run package entrypoint"
	@echo "  clean     - Remove local artifacts"

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

clean:
	rm -rf .venv .mypy_cache .ruff_cache .pytest_cache build dist *.egg-info coverage.xml .coverage
