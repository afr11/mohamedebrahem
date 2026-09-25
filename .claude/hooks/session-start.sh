#!/bin/bash
# Installs the project's Python toolkit in Claude Code on the web sessions.
set -euo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

cd "$CLAUDE_PROJECT_DIR"
pip install --quiet --disable-pip-version-check -r requirements.txt
