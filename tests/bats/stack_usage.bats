#!/usr/bin/env bats
# BATS smoke tests for stack.sh (run: bats tests/bats/stack_usage.bats)

@test "stack.sh invalid command exits 1" {
  run bash "${BATS_TEST_DIRNAME}/../../stack.sh" invalid-command-xyz
  [ "$status" -eq 1 ]
}
