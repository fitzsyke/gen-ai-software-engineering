---
description: Validate all transactions in sample-transactions.json without running the full pipeline
---

Validate all transactions in `sample-transactions.json` without processing them through the full pipeline.

Steps:
1. Run the validator stage in dry-run mode: `python -m pipeline.validator --dry-run sample-transactions.json` (or the equivalent invocation for however `pipeline/validator.py` exposes a dry-run/CLI entrypoint — check the file if unsure).
2. Report: total transaction count, valid count, invalid count, and the specific rejection reason for each invalid transaction (e.g. `invalid_currency`, `invalid_amount`, `missing_field:<name>`).
3. Show the results as a markdown table with columns: `transaction_id`, `status` (valid/invalid), `reason`. Mask account identifiers to last-4 if they appear anywhere in the output — never print full account numbers.
