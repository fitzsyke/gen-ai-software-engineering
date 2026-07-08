#!/usr/bin/env bash
# PreToolUse hook: blocks `git push` if pytest coverage on pipeline/orchestrator is below the required gate.
set -euo pipefail

MIN_COVERAGE=80
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

INPUT="$(cat)"
COMMAND="$(printf '%s' "$INPUT" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("tool_input", {}).get("command", ""))' 2>/dev/null || echo "")"

# Only act on commands that actually push to a remote.
if ! printf '%s' "$COMMAND" | grep -Eq '(^|[; &|])git[[:space:]]+push([[:space:]]|$)'; then
  exit 0
fi

cd "$PROJECT_DIR"

if [ ! -d pipeline ] && [ ! -f orchestrator.py ]; then
  # Nothing to test yet — don't block early scaffolding pushes.
  exit 0
fi

set +e
COV_OUTPUT="$(python3 -m pytest --cov=pipeline --cov=orchestrator --cov-report=term-missing --cov-fail-under="$MIN_COVERAGE" -q 2>&1)"
STATUS=$?
set -e

echo "$COV_OUTPUT" >&2

if [ $STATUS -ne 0 ]; then
  echo "" >&2
  echo "BLOCKED: test suite failed or coverage is below the required ${MIN_COVERAGE}% gate. Push denied." >&2
  exit 2
fi

exit 0
