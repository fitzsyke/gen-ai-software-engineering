# Agent Operating Instructions — Transaction Processing Pipeline Capstone

> These instructions govern how any AI coding agent operates within this codebase. They override default assistant behavior where they conflict. They are not optional suggestions, and they are not a changelog of what has been built — they are the durable rules of this repo.

---

## 1. The Four Agents

| Agent | Role | Produces | Consumes |
|-------|------|----------|----------|
| **Agent 1 — Specification** | Defines what the pipeline must do | `specification.md`, `agents.md` | `sample-transactions.json`, this file |
| **Agent 2 — Code Generation** | Builds the pipeline and front-end | `orchestrator.py`, `pipeline/*.py`, `frontend/`, `research-notes.md` | `specification.md` |
| **Agent 3 — Unit Tests** | Verifies the pipeline works and is covered | `tests/*` | `specification.md`, the actual `pipeline/*.py` source |
| **Agent 4 — Documentation** | Explains the finished system | `README.md`, `HOWTORUN.md` | Everything above — must reflect what actually exists, not what was planned |

Each agent operates strictly within its own column. An agent asked to do another agent's job must decline and name the correct agent instead of quietly doing the work.

---

## 2. Handoff Order (Non-Negotiable)

```
Agent 1 (spec) ──▶ Agent 2 (code) ──▶ Agent 3 (tests) ──▶ Agent 4 (docs)
```

- Agent 2 must not start implementing a stage until that stage has a `Task:` block in `specification.md`. If the spec is silent or ambiguous on a business rule (e.g. an exact fraud-score weight), Agent 2 must treat the spec's `[PLACEHOLDER]` as authoritative and not invent a number — flag it back to Agent 1 rather than guessing.
- Agent 3 must not weaken pipeline behavior (loosen a validation check, catch-and-ignore an exception) merely to make a test pass. A failing test against correct behavior is a bug report, not a license to edit `pipeline/`.
- Agent 4 must not describe a stage, endpoint, or skill that doesn't exist in the repo yet. If `specification.md` promises something Agent 2 hasn't built, the docs describe reality and note the gap.
- No agent edits another agent's required output files (see table in §1) except to fix something that blocks its own deliverable — and even then, flag it rather than silently rewriting.

---

## 3. Scope Boundaries — What Each Agent Must Never Touch

- **Agent 1** never writes `pipeline/*.py`, `orchestrator.py`, front-end code, tests, or `README.md`/`HOWTORUN.md`.
- **Agent 2** never writes `specification.md`, `agents.md`, or `README.md`/`HOWTORUN.md`, and does not write tests under `tests/` (it may run a quick manual sanity check on its own code, but the test suite is Agent 3's deliverable).
- **Agent 3** never writes `specification.md`, `agents.md`, or docs, and does not add new pipeline behavior — only tests for behavior that exists.
- **Agent 4** never writes application code, tests, or the spec.

---

## 4. Non-Negotiable Domain Constraints

These apply to every agent that touches money, currency, PII, or logging — regardless of which stage or file is involved.

### 4.1 Monetary Precision

- Every amount is parsed and stored as `decimal.Decimal`, constructed directly from the original string in the JSON record (e.g. `Decimal("75000.00")`, `Decimal("-100.00")`) — never via `float()` first.
- `float`, native binary-floating arithmetic, or rounding via `Math.round`-style calls are forbidden anywhere an amount is compared, summed, or persisted.
- Concrete cases the pipeline must handle correctly (from `sample-transactions.json`): `TXN002`/`TXN005` are high-value wire transfers (`25000.00`, `75000.00`) that must trigger fraud review; `TXN007` is a **negative** amount (`-100.00`) on a `refund` — negative is expected and valid for `transaction_type: "refund"`, but a negative amount on any other `transaction_type` must be rejected by validation.

### 4.2 Currency Codes

- Every currency must be validated against the ISO 4217 alpha-3 list. `TXN006` uses `"XYZ"`, which is not a real ISO 4217 code — this is the canonical example of a transaction the validator must reject with a clear reason, not silently pass through.
- Never accept a free-text or lowercase currency string; normalize case but do not invent unlisted codes.

### 4.3 PII Handling

- `source_account` and `destination_account` (e.g. `ACC-1001`) are PII. They must never appear in plaintext in log lines, `research-notes.md`, or documentation examples.
- Mask to last 4 characters when a stage needs to reference an account in a log (e.g. `ACC-1001` → `...1001`). The raw JSON records passed between pipeline stages via `shared/` may contain the full value (that's the data contract), but anything written to a log stream or printed to console must be masked.
- No agent should copy real-looking account numbers from `sample-transactions.json` into docs or comments as "example" data without masking them the same way.

### 4.4 Logging Schema

- Every pipeline stage emits one structured log line per transaction it processes, containing at minimum: an ISO 8601 timestamp, the stage name, the `transaction_id`, and the outcome (e.g. `validated`, `rejected: invalid_currency`, `flagged: high_value`).
- Log timestamps are the time the stage processed the record, not the transaction's own `timestamp` field — don't conflate the two.

### 4.5 File-Based Pipeline Protocol

- Stages communicate **only** by reading/writing JSON message envelopes through `shared/input/ → shared/processing/ → shared/output/ → shared/results/`. Direct in-memory function-to-function calls between stage modules (bypassing the file handoff) are forbidden, even though the orchestrator itself may invoke each stage's entrypoint directly.
- The envelope schema (`message_id`, `timestamp`, `source_stage`, `target_stage`, `message_type`, `data`) is defined in `specification.md` and must not be altered by Agent 2 without Agent 1 updating the spec first.

---

## 5. Testing Expectations (Agent 3, enforced by hook)

- Coverage gate: `pytest --cov=pipeline --cov=orchestrator` must report **≥ 80%** — this is a hard, hook-enforced gate that blocks `git push` (see `.claude/hooks/`). Target ≥ 90% per the spec's Context section.
- Tests must never read/write the real `shared/` directories; use a temp directory and point the code under test at it.
- At minimum, ground test cases in real edge cases already present in `sample-transactions.json`: invalid currency (`TXN006`), negative amount on a non-refund vs. valid negative on a refund (`TXN007`), high-value transactions over $10,000 (`TXN002`, `TXN003`, `TXN005`), a cross-border/off-hours transaction (`TXN004`: 02:47 UTC, Germany), and an ordinary happy-path transfer (`TXN001`, `TXN008`).

---

## 6. Documentation Expectations (Agent 4)

- `README.md` must include an author line ("Created by Artem Saienko" or equivalent) — hard grading requirement, never omit it.
- Every claim in `README.md`/`HOWTORUN.md` must be verifiable against the actual repo state at the time of writing (real file names, real stage order, real skill/MCP names) — not the aspirational plan from `specification.md`.

---

## 7. MCP and Skills Context

- `mcp.json` wires in `context7` (library docs lookup, used by Agent 2 — at least 2 queries must be logged in `research-notes.md`) and `pipeline-status` (`mcp/server.py`, a project-local MCP server for inspecting pipeline state).
- Two slash commands govern operational workflows: `/run-pipeline` (full end-to-end run) and `/validate-transactions` (validation-only dry run). Agent 4 documents how to invoke both in `HOWTORUN.md`; no agent should reimplement their logic elsewhere — they are the canonical entry points.

---

## 8. When a Rule Is Ambiguous

If the assignment or the user hasn't settled a concrete business rule (an exact fraud-score threshold, a specific compliance check beyond the required minimum), the correct move is a clearly labeled placeholder or assumption in `specification.md` — never a silently invented number baked directly into code, tests, or docs.
