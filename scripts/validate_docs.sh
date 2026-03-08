#!/usr/bin/env bash
# validate_docs.sh — Run the internalCMDB metadata validator on one or more documents or directories.
#
# Usage:
#   ./scripts/validate_docs.sh [--strict] [--verbose] <target> [<target2> ...]
#
# Options:
#   --strict     Enable strict validation (cross-reference checks, binding target validation)
#   --verbose    Verbose output (implied when running on a single file)
#   --help       Show this help message
#
# Examples:
#   ./scripts/validate_docs.sh docs/adr/ADR-006.md
#   ./scripts/validate_docs.sh --strict docs/
#   ./scripts/validate_docs.sh docs/adr/ docs/governance/
#
# Exit codes:
#   0  All documents valid
#   1  One or more documents have errors
#   2  Usage error or missing prerequisites

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
VENV_PYTHON="${REPO_ROOT}/.venv/bin/python"
VALIDATOR_MODULE="internalcmdb.governance.metadata_validator"

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

STRICT=0
VERBOSE=0
TARGETS=()

for arg in "$@"; do
  case "$arg" in
    --strict)   STRICT=1 ;;
    --verbose|-v) VERBOSE=1 ;;
    --help|-h)
      sed -n '2,20p' "$0" | sed 's/^# //'
      exit 0
      ;;
    -*)
      echo "Unknown option: $arg" >&2
      exit 2
      ;;
    *)
      TARGETS+=("$arg")
      ;;
  esac
done

if [[ ${#TARGETS[@]} -eq 0 ]]; then
  echo "Error: no target specified." >&2
  echo "Usage: $0 [--strict] [--verbose] <target> [<target2> ...]" >&2
  exit 2
fi

# Single file → always verbose
if [[ ${#TARGETS[@]} -eq 1 && -f "${TARGETS[0]}" ]]; then
  VERBOSE=1
fi

# ---------------------------------------------------------------------------
# Prerequisites check
# ---------------------------------------------------------------------------

if [[ ! -x "${VENV_PYTHON}" ]]; then
  echo "Error: virtual environment Python not found at ${VENV_PYTHON}" >&2
  echo "Run: python -m venv .venv && .venv/bin/pip install -e '.[dev]'" >&2
  exit 2
fi

# ---------------------------------------------------------------------------
# Build validator command
# ---------------------------------------------------------------------------

# Validator only accepts a single target path — run once per target
FAIL=0
for target in "${TARGETS[@]}"; do
  # When scanning a directory, skip docs/templates/ — templates contain placeholder
  # values (YYYY-MM-DD, NNN) that are intentionally invalid until filled by an author.
  if [[ -d "${target}" ]]; then
    while IFS= read -r -d '' md_file; do
      # Skip template files (paths can be relative or absolute)
      if [[ "${md_file}" == *"docs/templates/"* ]]; then
        continue
      fi
      CMD=("${VENV_PYTHON}" -m "${VALIDATOR_MODULE}")
      [[ $STRICT -eq 1 ]] && CMD+=("--strict")
      [[ $VERBOSE -eq 1 ]] && CMD+=("-v")
      CMD+=("${md_file}")
      PYTHONPATH="${REPO_ROOT}/src" "${CMD[@]}" || FAIL=1
    done < <(find "${target}" -name "*.md" -print0)
  else
    CMD=("${VENV_PYTHON}" -m "${VALIDATOR_MODULE}")
    [[ $STRICT -eq 1 ]] && CMD+=("--strict")
    [[ $VERBOSE -eq 1 ]] && CMD+=("-v")
    CMD+=("${target}")
    PYTHONPATH="${REPO_ROOT}/src" "${CMD[@]}" || FAIL=1
  fi
done

exit $FAIL
