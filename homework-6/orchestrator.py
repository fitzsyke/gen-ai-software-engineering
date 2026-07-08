"""Orchestrator: sets up shared/ directories, loads sample-transactions.json,
runs the three pipeline stages in order, and writes a summary report.

Usage: python orchestrator.py [path/to/transactions.json]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from pipeline import fraud_detector, settlement, validator
from pipeline.common import (
    PROJECT_ROOT,
    RESULTS_DIR,
    SHARED_DIR,
    SUMMARY_FILE,
    ensure_shared_dirs,
    make_envelope,
    write_json,
)

DEFAULT_SAMPLE_FILE = PROJECT_ROOT / "sample-transactions.json"


def load_records(sample_file: Path, shared_dir: Path = SHARED_DIR) -> None:
    """Wrap each raw transaction record in an input envelope under shared/input/."""
    records = json.loads(sample_file.read_text())
    input_dir = shared_dir / "input"
    for record in records:
        envelope = make_envelope("orchestrator", "validator", "transaction", record)
        write_json(input_dir / f"{record['transaction_id']}.json", envelope)


def write_summary(shared_dir: Path = SHARED_DIR) -> dict:
    results_dir = shared_dir / "results"
    summary_path = shared_dir / "results" / "pipeline_summary.json"

    counts: dict[str, int] = {}
    rejected: list[dict] = []
    flagged: list[dict] = []

    for path in sorted(results_dir.glob("*.json")):
        if path.name == summary_path.name:
            continue
        record = json.loads(path.read_text())
        status = record.get("status", "unknown")
        counts[status] = counts.get(status, 0) + 1
        if status == "rejected":
            rejected.append({"transaction_id": record["transaction_id"], "reason": record.get("reason")})
        elif status == "flagged":
            flagged.append({
                "transaction_id": record["transaction_id"],
                "risk_score": record.get("risk_score"),
                "risk_factors": record.get("risk_factors"),
            })

    summary = {
        "total": sum(counts.values()),
        "counts_by_status": counts,
        "rejected": rejected,
        "flagged": flagged,
    }
    write_json(summary_path, summary)
    return summary


def run_pipeline(sample_file: Path = DEFAULT_SAMPLE_FILE, shared_dir: Path = SHARED_DIR) -> dict:
    ensure_shared_dirs(shared_dir)
    load_records(sample_file, shared_dir)
    validator.run_stage(shared_dir)
    fraud_detector.run_stage(shared_dir)
    settlement.run_stage(shared_dir)
    return write_summary(shared_dir)


if __name__ == "__main__":
    sample_arg = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_SAMPLE_FILE
    if not sample_arg.exists():
        print(f"Error: sample file not found: {sample_arg}", file=sys.stderr)
        sys.exit(1)

    summary = run_pipeline(sample_arg)
    print()
    print("Pipeline run complete.")
    print(json.dumps(summary, indent=2))
