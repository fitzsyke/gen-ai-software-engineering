"""Validation stage: checks required fields, amount, and currency.

Reads validated envelopes from shared/input/, writes passing transactions to
shared/output/ (source_stage=validator, target_stage=fraud_detector) and
rejected transactions straight to shared/results/ (status=rejected).
"""
from __future__ import annotations

import argparse
import json
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path

from pipeline.common import (
    ISO_4217_CURRENCIES,
    REQUIRED_FIELDS,
    SHARED_DIR,
    log_event,
    make_envelope,
    mask_account,
    read_json,
    write_json,
)

STAGE_NAME = "validator"


def validate_transaction(record: dict) -> dict:
    """Validate one raw transaction record.

    Returns the record augmented with:
      - "valid": bool
      - "reason": str | None -- present (and non-None) only when invalid
    Never mutates the input dict's account fields; amount stays a string.
    """
    result = dict(record)

    for field in REQUIRED_FIELDS:
        value = record.get(field)
        if value is None or value == "":
            return {**result, "valid": False, "reason": f"missing_field:{field}"}

    currency = record["currency"]
    if currency not in ISO_4217_CURRENCIES:
        return {**result, "valid": False, "reason": "invalid_currency"}

    amount_str = record["amount"]
    try:
        amount = Decimal(str(amount_str))
    except (InvalidOperation, ValueError):
        return {**result, "valid": False, "reason": "invalid_amount"}

    if amount < 0 and record.get("transaction_type") != "refund":
        return {**result, "valid": False, "reason": "invalid_amount"}

    return {**result, "valid": True, "reason": None}


def run_stage(shared_dir: Path = SHARED_DIR) -> None:
    """File-I/O wrapper: drains shared/input/, applies validate_transaction,
    routes to shared/output/ or shared/results/."""
    input_dir = shared_dir / "input"
    processing_dir = shared_dir / "processing"
    output_dir = shared_dir / "output"
    results_dir = shared_dir / "results"

    envelope_files = sorted(input_dir.glob("*.json"))
    for envelope_path in envelope_files:
        envelope = read_json(envelope_path)
        processing_path = processing_dir / envelope_path.name
        processing_path.write_text(json.dumps(envelope))
        envelope_path.unlink()

        record = envelope["data"]
        transaction_id = record.get("transaction_id", envelope_path.stem)
        result = validate_transaction(record)

        if result["valid"]:
            out_envelope = make_envelope(STAGE_NAME, "fraud_detector", "transaction", result)
            write_json(output_dir / f"{transaction_id}.json", out_envelope)
            log_event(STAGE_NAME, transaction_id, "validated")
        else:
            # Terminal records in shared/results/ are flat (not envelope-wrapped)
            # so mcp/server.py and the front-end can read status/fields directly.
            terminal = {**result, "status": "rejected"}
            write_json(results_dir / f"{transaction_id}.json", terminal)
            log_event(
                STAGE_NAME,
                transaction_id,
                f"rejected:{result['reason']}",
                source_account=mask_account(record.get("source_account")),
            )

        processing_path.unlink(missing_ok=True)


def _dry_run(sample_file: Path) -> None:
    """CLI entrypoint for the /validate-transactions skill: validates the raw
    sample file in-memory without touching shared/ at all."""
    records = json.loads(sample_file.read_text())
    rows = []
    valid_count = 0
    for record in records:
        result = validate_transaction(record)
        status = "valid" if result["valid"] else "invalid"
        if result["valid"]:
            valid_count += 1
        rows.append((record.get("transaction_id", "?"), status, result.get("reason") or "-"))

    print(f"Total: {len(records)}  Valid: {valid_count}  Invalid: {len(records) - valid_count}")
    print()
    print(f"{'transaction_id':<16}{'status':<10}reason")
    for transaction_id, status, reason in rows:
        print(f"{transaction_id:<16}{status:<10}{reason}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Validation stage")
    parser.add_argument("sample_file", nargs="?", default="sample-transactions.json")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.dry_run:
        _dry_run(Path(args.sample_file))
    else:
        run_stage()
