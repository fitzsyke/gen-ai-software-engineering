#!/usr/bin/env bash
#
# run-pipeline.sh — single-command entry point for the 4-agent pipeline.
#
# Order: Bug Research Verifier -> Bug Fixer -> Security Verifier -> Unit Test Generator
# (Bug Researcher and Bug Planner already ran ahead of time and produced
#  research/codebase-research.md and implementation-plan.md, which are committed inputs.)
#
# Each agent is defined in agents/*.agent.md. This script reads each agent's frontmatter
# (model, tools) and system-prompt body directly from that file and passes them to a
# non-interactive `claude -p` session, so no agent is invoked by hand and each agent loads
# its own referenced skill file(s) itself as its first instructed step.
#
# Usage: ./run-pipeline.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

AGENTS_DIR="agents"
LOG_DIR="docs/pipeline-logs"
mkdir -p "$LOG_DIR"

if ! command -v claude >/dev/null 2>&1; then
  echo "ERROR: 'claude' CLI not found on PATH. Install Claude Code first." >&2
  exit 1
fi

# --- helpers ---------------------------------------------------------------

# Print everything between the first and second '---' lines (YAML frontmatter).
frontmatter_of() {
  awk '/^---[[:space:]]*$/{c++; next} c==1' "$1"
}

# Print everything after the second '---' line (the agent's instruction body).
body_of() {
  awk 'BEGIN{c=0} /^---[[:space:]]*$/{c++; next} c>=2' "$1"
}

field_of() {
  # $1 = frontmatter text, $2 = field name (e.g. "model")
  awk -v f="$2:" '$0 ~ "^"f {sub("^"f"[ ]*", ""); print; exit}' <<<"$1"
}

tools_csv_of() {
  # $1 = frontmatter text -> comma-separated list from the YAML "tools:" block
  awk '
    /^tools:/ { f=1; next }
    f && /^  - / { sub(/^  - /, ""); list = list sep $0; sep="," ; next }
    f { f=0 }
    END { print list }
  ' <<<"$1"
}

# run_agent <label> <agent-file> <task-prompt> <expected-output-file>
run_agent() {
  local label="$1" agent_file="$2" prompt="$3" expected_output="$4"

  if [[ ! -f "$agent_file" ]]; then
    echo "ERROR: agent definition not found: $agent_file" >&2
    exit 1
  fi

  local fm body_file model tools
  fm="$(frontmatter_of "$agent_file")"
  model="$(field_of "$fm" "model")"
  tools="$(tools_csv_of "$fm")"

  body_file="$(mktemp)"
  body_of "$agent_file" >"$body_file"
  trap 'rm -f "$body_file"' RETURN

  echo
  echo "=============================================================="
  echo "==> [$label] model=$model tools=$tools"
  echo "==> skill file(s) referenced in $agent_file are loaded by the"
  echo "    agent itself as its first instructed step (no manual step)."
  echo "=============================================================="

  claude -p "$prompt" \
    --append-system-prompt-file "$body_file" \
    --model "$model" \
    --allowedTools "$tools" \
    --permission-mode bypassPermissions \
    --output-format text \
    | tee "$LOG_DIR/${label}.log"

  rm -f "$body_file"
  trap - RETURN

  if [[ ! -f "$expected_output" ]]; then
    echo "ERROR: [$label] did not produce expected output '$expected_output'." >&2
    exit 1
  fi
  echo "==> [$label] OK — wrote $expected_output"
}

# --- environment for tests --------------------------------------------------
# Bug Fixer and Unit Test Generator both run pytest, which needs a Fernet key.
if [[ -z "${VAULT_KEY:-}" ]]; then
  export VAULT_KEY
  VAULT_KEY="$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")"
  echo "==> Generated ephemeral VAULT_KEY for this pipeline run."
fi

# --- preconditions -----------------------------------------------------------
if [[ ! -f research/codebase-research.md ]]; then
  echo "ERROR: research/codebase-research.md not found (Bug Researcher output required as pipeline input)." >&2
  exit 1
fi
if [[ ! -f implementation-plan.md ]]; then
  echo "ERROR: implementation-plan.md not found (Bug Planner output required as pipeline input)." >&2
  exit 1
fi

# --- stage 1: Bug Research Verifier ------------------------------------------
run_agent "1-research-verifier" \
  "$AGENTS_DIR/research-verifier.agent.md" \
  "Verify research/codebase-research.md against the live source tree (src/, tests/), following your role instructions and the rubric in skills/research-quality-measurement.md exactly. Write the full report to research/verified-research.md." \
  "research/verified-research.md"

# --- stage 2: Bug Fixer -------------------------------------------------------
run_agent "2-bug-fixer" \
  "$AGENTS_DIR/bug-fixer.agent.md" \
  "Execute implementation-plan.md task by task exactly as written. Apply each specified change, run the test command after every task, and stop immediately (without attempting your own fix) if a test fails. Write fix-summary.md documenting every change and the final status." \
  "fix-summary.md"

# --- stage 3: Security Vulnerabilities Verifier (on changed code) -----------
run_agent "3-security-verifier" \
  "$AGENTS_DIR/security-verifier.agent.md" \
  "Read fix-summary.md and review only the files it lists as changed for security issues, following your role instructions. Write security-report.md. Do not edit any code." \
  "security-report.md"

# --- stage 4: Unit Test Generator (on changed code) --------------------------
run_agent "4-unit-test-generator" \
  "$AGENTS_DIR/unit-test-generator.agent.md" \
  "Read fix-summary.md and skills/unit-tests-FIRST.md, then add unit tests for exactly the new/changed behavior described in fix-summary.md, following the FIRST rubric and the project's existing pytest conventions. Run the full test suite and write test-report.md." \
  "test-report.md"

echo
echo "=============================================================="
echo "Pipeline complete. Outputs:"
echo "  - research/verified-research.md"
echo "  - fix-summary.md"
echo "  - security-report.md"
echo "  - test-report.md"
echo "Per-stage logs saved under $LOG_DIR/"
echo "=============================================================="
