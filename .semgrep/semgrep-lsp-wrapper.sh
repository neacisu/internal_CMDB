#!/bin/bash
# shellcheck shell=bash
# Wrapper for the Semgrep extension LSP.
# Ensures pysemgrep and semgrep-core (from isolated venv) are on PATH
# before delegating to the bundled osemgrep-pro binary.
#
# Why: semgrep.semgrep VS Code extension ships osemgrep-pro (OCaml).
# When osemgrep-pro needs Python fallback for LSP it calls `pysemgrep`
# from PATH. Without this wrapper it fails with:
#   execvp pysemgrep: No such file or directory
#
# Usage: set "semgrep.path": "/opt/stacks/internalcmdb/.semgrep/semgrep-lsp-wrapper.sh"
# in .vscode/settings.json

export PATH="/opt/semgrep-venv/bin:$PATH"

OSEMGREP="/root/.vscode-server-insiders/extensions/semgrep.semgrep-1.16.0-linux-x64/dist/osemgrep-pro"

exec "$OSEMGREP" "$@"
