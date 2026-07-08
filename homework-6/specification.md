# Specification — AI-Powered Transaction Processing Pipeline

## 1. High-Level Objective

A file-based pipeline that ingests raw transaction records, validates them, scores them for fraud risk, and settles the surviving transactions, producing an auditable trail of results and a summary report.

---

## 2. Mid-Level Objectives

- Every transaction in `sample-transactions.json` is validated for required fields, a parseable positive-or-refund-appropriate decimal `amount`, and an ISO 4217 `currency`; invalid records are written to `shared/results/` with a `status: "rejected"` and a machine-readable `reason` (e.g. `invalid_currency`, `invalid_amount`, `missing_field:<name>`).
- Transactions with `amount` (absolute value) above **$10,000**, or matching cross-border/off-hours risk patterns, are flagged for fraud review with a numeric `risk_score` (0–100) and one or more `risk_factors`.
- Transactions that pass validation and are not blocked by fraud review are settled, producing a final `status: "settled"` record in `shared/results/` with a settlement timestamp.
- All pipeline stages log every transaction they touch with an ISO 8601 timestamp, the stage name, the `transaction_id`, and the outcome — never the raw account numbers.
- Running `python orchestrator.py` end-to-end processes all 8 records in `sample-transactions.json` with no unhandled exceptions, and every input transaction has exactly one corresponding terminal record in `shared/results/`.

---

## 3. Implementation Notes

- **Monetary values**: every `amount` is parsed into `decimal.Decimal` directly from its JSON string (e.g. `Decimal("75000.00")`). `float`/`int` arithmetic on money is forbidden anywhere in the pipeline.
- **Currency codes**: validated against a fixed ISO 4217 alpha-3 allowlist (`USD`, `EUR`, `GBP`, `JPY`, `CAD`, `AUD`, `CHF`, `CNY`, and any others actually present in `sample-transactions.json`). Codes not on the allowlist (e.g. `XYZ`) are rejected, never silently passed through.
- **Logging**: every stage emits one structured JSON log line per transaction processed: `{"timestamp": "<ISO 8601>", "stage": "<stage_name>", "transaction_id": "<id>", "outcome": "<outcome>"}`.
- **PII**: `source_account` and `destination_account` are never logged or printed in plaintext. When a stage needs to reference an account outside the raw JSON record payload (e.g. in a log line or CLI report), mask to last 4 characters (`ACC-1001` → `...1001`).
- **File-based pipeline protocol**: stages communicate exclusively via JSON message envelopes moved through `shared/input/ → shared/processing/ → shared/output/ → shared/results/`. No stage calls another stage's function directly; the orchestrator invokes each stage's entrypoint, and each stage reads its input from files.
- **Refund exception to amount sign**: a negative `amount` is valid only when `transaction_type == "refund"`. A negative amount on any other `transaction_type` is a validation failure (`invalid_amount`).
- **[PLACEHOLDER]** Exact fraud-scoring weights (how much a cross-border transfer, an off-hours timestamp, and a high-value amount each contribute to `risk_score`) are not specified by the assignment. Agent 2 must implement a documented, deterministic scoring function (see Task: Fraud Detection below) rather than inventing unstated business thresholds and presenting them as settled requirements. A reasonable default is provided in the Low-Level Task below and may be adjusted, but the exact weights are an assumption, not a hard requirement.
- **[PLACEHOLDER]** Settlement in this capstone is simulated (no real payment rail integration) — "settling" a transaction means writing a terminal `status: "settled"` record with a settlement timestamp, not calling any external system.

---

## 4. Context

### Beginning state

- `sample-transactions.json` at the project root: 8 raw transaction records, each with `transaction_id`, `timestamp`, `source_account`, `destination_account`, `amount` (string), `currency`, `transaction_type`, `description`, and `metadata.{channel,country}`.
- Known edge cases already present in the sample data that every stage must handle correctly:
  - `TXN002` (`25000.00 USD`, `wire_transfer`) and `TXN005` (`75000.00 USD`, `wire_transfer`) — high-value, must be fraud-flagged.
  - `TXN003` (`9999.99 USD`) — just under the $10,000 threshold; must pass through as a normal (non-flagged) high-value-adjacent transaction, exercising the boundary.
  - `TXN004` (`500.00 EUR`, `02:47 UTC`, `country: DE`) — cross-border and off-hours; must be fraud-flagged even though the amount is small.
  - `TXN006` (`200.00 XYZ`) — invalid ISO 4217 currency; must be rejected at validation.
  - `TXN007` (`-100.00 GBP`, `refund`) — negative amount valid because `transaction_type == "refund"`.
  - `TXN001`, `TXN008` — ordinary happy-path transfers; must validate, pass fraud review, and settle cleanly.
- Empty directory scaffolding already exists: `shared/{input,processing,output,results}/`, `pipeline/__init__.py`, `frontend/`, `tests/`.

### Ending state

- All 8 transactions from `sample-transactions.json` have a terminal JSON record in `shared/results/`, each with at least `transaction_id`, `status` (`settled` | `rejected` | `flagged`), and stage-specific fields (`reason` for rejected, `risk_score`/`risk_factors` for flagged).
- `shared/results/pipeline_summary.json` — a single summary report: total count, counts by terminal status, and a list of rejected/flagged transaction IDs with reasons.
- A simple web front-end (Flask) under `frontend/` that triggers a pipeline run and/or displays `shared/results/` contents.
- Test suite under `tests/` with coverage ≥ 80% (gate) targeting ≥ 90%, covering all three stages plus one full-pipeline integration test.

### Message envelope schema

Every JSON file moved between `shared/input/`, `shared/processing/`, and `shared/output/` uses this envelope. Terminal records written to `shared/results/` are the flat `data` payload only (no envelope wrapper), so the `pipeline-status` MCP server and the front-end can read `status`/`reason`/`risk_score` directly:

```json
{
  "message_id": "uuid4-string",
  "timestamp": "2026-03-16T10:00:00Z",
  "source_stage": "validator",
  "target_stage": "fraud_detector",
  "message_type": "transaction",
  "data": {
    "transaction_id": "TXN001",
    "amount": "1500.00",
    "currency": "USD",
    "status": "validated"
  }
}
```

- `message_id`: newly generated `uuid4` per envelope (not reused across stages).
- `timestamp`: ISO 8601, time the envelope was written.
- `source_stage`/`target_stage`: the stage that produced it and the stage that should consume it next (`"results"` as a terminal pseudo-stage for `shared/results/` writes).
- `data`: the full transaction record plus any fields the producing stage added (`status`, `reason`, `risk_score`, `risk_factors`, `settled_at`, etc.), carried forward by each subsequent stage.

---

## 5. Low-Level Tasks

```
Task: Validation Stage
Prompt: "Implement pipeline/validator.py with validate_transaction(record: dict) -> dict, reading transaction envelopes from shared/input/, checking required fields (transaction_id, timestamp, source_account, destination_account, amount, currency, transaction_type), a parseable decimal amount (Decimal, positive unless transaction_type == 'refund', in which case negative is allowed), and an ISO 4217 currency against a fixed allowlist. Write a validated envelope to shared/output/ (source_stage=validator, target_stage=fraud_detector) on success, or a rejected envelope to shared/results/ (status=rejected, reason=<invalid_currency|invalid_amount|missing_field:<name>>) on failure. Support a --dry-run CLI mode that validates sample-transactions.json directly and prints a report without writing files, for the /validate-transactions skill."
File to CREATE: pipeline/validator.py
Function to CREATE: validate_transaction(record: dict) -> dict
Details: Required fields must all be present and non-empty. Amount must parse as decimal.Decimal from its string form (reject non-numeric or malformed strings). Amount sign: negative only permitted when transaction_type == "refund". Currency must be in the ISO 4217 allowlist (reject e.g. "XYZ"). Every check emits a structured log line (timestamp, stage="validator", transaction_id, outcome). Never log source_account/destination_account in plaintext — mask to last 4 chars if referenced in a log or CLI report.

Task: Fraud Detection Stage
Prompt: "Implement pipeline/fraud_detector.py with score_transaction(record: dict) -> dict, reading validated envelopes from shared/output/ (produced by the validator), computing a risk_score (0-100) from: amount over $10,000 absolute value (+60), cross-border transaction where metadata.country differs from the domestic reference market (+30), and off-hours timestamp (00:00-05:00 UTC) (+30). Transactions with risk_score >= 50 are flagged (status=flagged) and written to shared/results/ with risk_score and risk_factors (list of triggered rules); transactions below threshold are passed through to shared/output/ for settlement (source_stage=fraud_detector, target_stage=settlement)."
File to CREATE: pipeline/fraud_detector.py
Function to CREATE: score_transaction(record: dict) -> dict
Details: [PLACEHOLDER weights, see Implementation Notes] — must be deterministic and documented in code comments. TXN002, TXN005 (high-value) and TXN004 (cross-border + off-hours) must score >= 50 given the default weights; TXN001, TXN003, TXN007, TXN008 must score below 50. Emits structured log line per transaction (timestamp, stage="fraud_detector", transaction_id, outcome=flagged|passed, risk_score).

Task: Settlement Stage
Prompt: "Implement pipeline/settlement.py with settle_transaction(record: dict) -> dict, reading fraud-cleared envelopes from shared/output/ (produced by fraud_detector), and writing a terminal settled record to shared/results/ with status=settled and a settled_at ISO 8601 timestamp. No real payment rail integration — this is a simulated settlement that finalizes the record."
File to CREATE: pipeline/settlement.py
Function to CREATE: settle_transaction(record: dict) -> dict
Details: Adds settled_at (ISO 8601, time of settlement) to the record and writes it to shared/results/ as the terminal record. Emits structured log line (timestamp, stage="settlement", transaction_id, outcome="settled"). After all stages run, the orchestrator additionally writes shared/results/pipeline_summary.json aggregating total count, counts by status, and rejected/flagged transaction IDs with reasons/risk_scores.
```
