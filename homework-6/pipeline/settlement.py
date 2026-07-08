"""Settlement stage: finalizes fraud-cleared transactions.

Reads envelopes from shared/output/ (target_stage=settlement, written by
fraud_detector) and writes a terminal settled record to shared/results/.
This is a simulated settlement -- no external payment rail integration,
per specification.md's [PLACEHOLDER] note.
"""
from __future__ import annotations

from pathlib import Path

from pipeline.common import SHARED_DIR, log_event, now_iso, read_json, write_json

STAGE_NAME = "settlement"


def settle_transaction(record: dict) -> dict:
    """Finalize a fraud-cleared transaction with a settlement timestamp."""
    result = dict(record)
    result["status"] = "settled"
    result["settled_at"] = now_iso()
    return result


def run_stage(shared_dir: Path = SHARED_DIR) -> None:
    output_dir = shared_dir / "output"
    results_dir = shared_dir / "results"

    envelope_files = sorted(output_dir.glob("*.json"))
    for envelope_path in envelope_files:
        envelope = read_json(envelope_path)
        if envelope.get("target_stage") != "settlement":
            continue

        record = envelope["data"]
        transaction_id = record.get("transaction_id", envelope_path.stem)
        settled = settle_transaction(record)

        # Terminal records in shared/results/ are flat (not envelope-wrapped)
        # so mcp/server.py and the front-end can read status/fields directly.
        write_json(results_dir / f"{transaction_id}.json", settled)
        envelope_path.unlink()
        log_event(STAGE_NAME, transaction_id, "settled")
