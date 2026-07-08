---
description: Run the transaction processing pipeline end-to-end and summarize results
---

Run the transaction processing pipeline end-to-end.

Steps:
1. Check that `sample-transactions.json` exists at the project root. If it doesn't, stop and report the error.
2. Clear the `shared/` directories (`shared/input/`, `shared/processing/`, `shared/output/`, `shared/results/`), recreating them empty so this is a clean run.
3. Run the pipeline: `python orchestrator.py`.
4. Read every result file in `shared/results/` (including `pipeline_summary.json` if present) and show a summary: total transactions processed, counts by status (approved/rejected/flagged).
5. Report any transactions that were rejected or flagged, including their `transaction_id` and `reason`/`risk_score`. Mask account identifiers to last-4 in the report — never print full account numbers.
