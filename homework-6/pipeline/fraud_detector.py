"""Fraud detection stage: scores validated transactions for risk.

Reads envelopes from shared/output/ (written by validator), scores each
transaction, and either writes a flagged terminal record to shared/results/
or passes it through to shared/output/ (source_stage=fraud_detector,
target_stage=settlement) for the settlement stage to pick up.

Scoring weights below are a documented default, not a hard business
requirement -- see specification.md's [PLACEHOLDER] note on fraud-scoring
weights.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from pathlib import Path

from pipeline.common import (
    HIGH_VALUE_THRESHOLD,
    OFF_HOURS_END_UTC,
    OFF_HOURS_START_UTC,
    SHARED_DIR,
    log_event,
    make_envelope,
    read_json,
    write_json,
)

STAGE_NAME = "fraud_detector"
FLAG_THRESHOLD = 50

HIGH_VALUE_WEIGHT = 60
CROSS_BORDER_WEIGHT = 30
OFF_HOURS_WEIGHT = 30

# Domestic reference market: transactions whose metadata.country differs
# from this are treated as cross-border. Adjust if the pipeline is deployed
# for a different home market.
DOMESTIC_COUNTRY = "US"


def _is_off_hours(timestamp: str) -> bool:
    hour = datetime.fromisoformat(timestamp.replace("Z", "+00:00")).hour
    return OFF_HOURS_START_UTC <= hour < OFF_HOURS_END_UTC


def score_transaction(record: dict) -> dict:
    """Compute a risk_score (0-100) and risk_factors for a validated transaction."""
    result = dict(record)
    risk_factors: list[str] = []
    score = 0

    amount = Decimal(str(record["amount"]))
    if abs(amount) > HIGH_VALUE_THRESHOLD:
        score += HIGH_VALUE_WEIGHT
        risk_factors.append("high_value")

    country = record.get("metadata", {}).get("country")
    if country and country != DOMESTIC_COUNTRY:
        score += CROSS_BORDER_WEIGHT
        risk_factors.append("cross_border")

    if _is_off_hours(record["timestamp"]):
        score += OFF_HOURS_WEIGHT
        risk_factors.append("off_hours")

    result["risk_score"] = min(score, 100)
    result["risk_factors"] = risk_factors
    result["flagged"] = result["risk_score"] >= FLAG_THRESHOLD
    return result


def run_stage(shared_dir: Path = SHARED_DIR) -> None:
    output_dir = shared_dir / "output"
    results_dir = shared_dir / "results"

    envelope_files = sorted(output_dir.glob("*.json"))
    for envelope_path in envelope_files:
        envelope = read_json(envelope_path)
        if envelope.get("target_stage") != "fraud_detector":
            continue

        record = envelope["data"]
        transaction_id = record.get("transaction_id", envelope_path.stem)
        scored = score_transaction(record)

        if scored["flagged"]:
            # Terminal records in shared/results/ are flat (not envelope-wrapped)
            # so mcp/server.py and the front-end can read status/fields directly.
            terminal = {**scored, "status": "flagged"}
            write_json(results_dir / f"{transaction_id}.json", terminal)
            envelope_path.unlink()
            log_event(
                STAGE_NAME, transaction_id, "flagged",
                risk_score=scored["risk_score"], risk_factors=scored["risk_factors"],
            )
        else:
            passed = {**scored, "status": "fraud_cleared"}
            out_envelope = make_envelope(STAGE_NAME, "settlement", "transaction", passed)
            write_json(output_dir / f"{transaction_id}.json", out_envelope)
            log_event(STAGE_NAME, transaction_id, "passed", risk_score=scored["risk_score"])
