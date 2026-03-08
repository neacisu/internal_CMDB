#!/usr/bin/env bash
set -euo pipefail

python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e ".[dev]"
pre-commit install --hook-type pre-commit --hook-type pre-push

if ! command -v gitleaks >/dev/null 2>&1; then
	echo "Warning: gitleaks is not installed. Install it to enable the pre-push secret scan."
fi

echo "Bootstrap complete. Activate with: source .venv/bin/activate"
echo "Installed git hooks: pre-commit, pre-push"
