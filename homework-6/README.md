# AI-Powered Transaction Processing Pipeline

> **Student Name:** Artem Saienko
> **Homework:** Homework 6: Capstone Project
> **AI Tools Used:** Claude Code (Claude Opus 4.8, Claude Sonnet 5)

---

A file-based transaction processing pipeline built as a four-agent AI workflow capstone. Raw transaction records are validated, scored for fraud risk, and settled through three independent stages that communicate only via JSON files, producing an auditable trail of results and a summary report. A Flask dashboard lets you trigger a run and inspect the outcome, and a custom MCP server exposes pipeline state as queryable tools/resources.

## Pipeline Stages

- **Validator** (`pipeline/validator.py`) — checks required fields, parses `amount` as `decimal.Decimal`, validates the currency against an ISO 4217 allowlist, and enforces that a negative amount is only valid for `transaction_type == "refund"`. Rejects with a machine-readable `reason` (e.g. `invalid_currency`, `invalid_amount`, `missing_field:<name>`).
- **Fraud Detector** (`pipeline/fraud_detector.py`) — scores validated transactions 0-100 from three factors (amount over $10,000, cross-border country, off-hours UTC timestamp) and flags anything scoring ≥ 50 for review with `risk_score` and `risk_factors`.
- **Settlement** (`pipeline/settlement.py`) — finalizes fraud-cleared transactions with a `settled_at` timestamp (simulated; no external payment rail).

## Architecture

```
sample-transactions.json
        │
        ▼
┌──────────────┐   shared/input/ → processing/ → output/   ┌───────────────┐
│ orchestrator │ ─────────────────────────────────────────▶│   validator   │
└──────────────┘                                            └───────┬───────┘
                                                                     │ shared/output/
                                                                     ▼
                                                             ┌───────────────┐
                                                             │ fraud_detector│
                                                             └───────┬───────┘
                                                     flagged │       │ cleared
                                                              ▼      ▼
                                                     shared/results/  shared/output/
                                                              ▲              │
                                                              │              ▼
                                                              │      ┌──────────────┐
                                                              └──────│  settlement  │
                                                                     └──────────────┘
                                                                             │
                                                                             ▼
                                                                shared/results/pipeline_summary.json
```

Each stage reads its input from files and writes its output to files — no in-process function calls cross stage boundaries. Intermediate handoffs (`input/ → processing/ → output/`) use a JSON envelope (`message_id`, `timestamp`, `source_stage`, `target_stage`, `data`); terminal records written to `shared/results/` are flat (unwrapped), so the front-end and the `pipeline-status` MCP server can read `status`/`reason`/`risk_score` directly.

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.12 |
| Money arithmetic | `decimal.Decimal` |
| Front-end | Flask + Jinja templates |
| Testing | pytest + pytest-cov |
| MCP (library docs) | context7 |
| MCP (custom server) | FastMCP (`mcp/server.py`) |
| Automation | Claude Code skills (`/write-spec`, `/run-pipeline`, `/validate-transactions`) + coverage-gate pre-push hook |

## Result on the Sample Data

Running the pipeline against `sample-transactions.json` (8 records) produces: 1 rejected (`TXN006`, invalid currency `XYZ`), 3 flagged (`TXN002`, `TXN005` high-value; `TXN004` cross-border + off-hours), 4 settled.

## Testing

29 tests across `tests/`, covering all three stages plus a full-pipeline integration test, at 94% coverage (gate: ≥ 80%, target: ≥ 90%). See `HOWTORUN.md` for how to run them.

## Project Documents

- `specification.md` — full technical specification (objectives, constraints, message schema, per-stage tasks)
- `agents.md` — operating rules for the four workflow agents (spec, code, tests, docs)
- `research-notes.md` — context7 queries used during code generation
- `HOWTORUN.md` — step-by-step setup and run instructions
