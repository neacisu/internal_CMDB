#!/usr/bin/env bats
# BATS tests for scripts/validate_docs.sh

setup() {
  SCRIPT="${BATS_TEST_DIRNAME}/../../scripts/validate_docs.sh"
}

@test "validate_docs.sh exits 2 with no arguments" {
  run bash "${SCRIPT}"
  [ "$status" -eq 2 ]
}

@test "validate_docs.sh exits 2 with unknown option" {
  run bash "${SCRIPT}" --unknown-option
  [ "$status" -eq 2 ]
}

@test "validate_docs.sh --help exits 0" {
  run bash "${SCRIPT}" --help
  [ "$status" -eq 0 ]
}

@test "validate_docs.sh -h exits 0" {
  run bash "${SCRIPT}" -h
  [ "$status" -eq 0 ]
}

@test "validate_docs.sh exits 2 when venv python is missing" {
  # Pass a real file but venv won't exist in test env
  run bash "${SCRIPT}" "${BATS_TEST_DIRNAME}/stack_usage.bats"
  # Should fail with 2 (missing prerequisites) since .venv doesn't exist
  [ "$status" -eq 2 ]
}
