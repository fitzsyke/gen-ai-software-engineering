"""Shared helpers for the transaction pipeline: paths, envelopes, logging, masking.

Every pipeline stage imports from here so the file-based protocol, logging
schema, and PII-masking rule are enforced identically across stages.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SHARED_DIR = PROJECT_ROOT / "shared"
INPUT_DIR = SHARED_DIR / "input"
PROCESSING_DIR = SHARED_DIR / "processing"
OUTPUT_DIR = SHARED_DIR / "output"
RESULTS_DIR = SHARED_DIR / "results"
SUMMARY_FILE = RESULTS_DIR / "pipeline_summary.json"

# ISO 4217 alpha-3 allowlist. Not exhaustive of every currency in existence,
# but covers every currency that legitimately appears in this pipeline's
# input data plus the common majors. "XYZ" (seen in sample-transactions.json)
# is deliberately absent -- it is not a real ISO 4217 code.
ISO_4217_CURRENCIES = frozenset(
    {
        "USD", "EUR", "GBP", "JPY", "CAD", "AUD", "CHF", "CNY",
        "SEK", "NOK", "DKK", "NZD", "SGD", "HKD", "INR", "MXN",
        "BRL", "ZAR", "KRW", "PLN",
    }
)

HIGH_VALUE_THRESHOLD = Decimal("10000")
OFF_HOURS_START_UTC = 0   # inclusive
OFF_HOURS_END_UTC = 5     # exclusive -- off-hours window is [00:00, 05:00) UTC

REQUIRED_FIELDS = (
    "transaction_id",
    "timestamp",
    "source_account",
    "destination_account",
    "amount",
    "currency",
    "transaction_type",
)


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def mask_account(account: str | None) -> str:
    """Mask an account identifier to its last 4 characters for logs/reports.

    Raw records moved through shared/ keep the full value (data contract);
    this is only for anything printed to a log line, console, or doc.
    """
    if not account:
        return "****"
    return f"...{account[-4:]}" if len(account) > 4 else account


def log_event(stage: str, transaction_id: str, outcome: str, **extra: Any) -> None:
    """Emit one structured JSON log line: timestamp, stage, transaction_id, outcome."""
    entry = {
        "timestamp": now_iso(),
        "stage": stage,
        "transaction_id": transaction_id,
        "outcome": outcome,
    }
    entry.update(extra)
    print(json.dumps(entry))


def make_envelope(source_stage: str, target_stage: str, message_type: str, data: dict) -> dict:
    return {
        "message_id": str(uuid.uuid4()),
        "timestamp": now_iso(),
        "source_stage": source_stage,
        "target_stage": target_stage,
        "message_type": message_type,
        "data": data,
    }


def write_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, default=str))


def read_json(path: Path) -> dict:
    return json.loads(path.read_text())


def ensure_shared_dirs(shared_dir: Path | None = None) -> None:
    base = shared_dir or SHARED_DIR
    for sub in ("input", "processing", "output", "results"):
        (base / sub).mkdir(parents=True, exist_ok=True)
