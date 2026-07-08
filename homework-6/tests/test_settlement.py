import json

from pipeline import settlement
from pipeline.common import make_envelope


def _cleared_record(**overrides):
    base = {
        "transaction_id": "TXN001",
        "timestamp": "2026-03-16T09:00:00Z",
        "source_account": "ACC-1001",
        "destination_account": "ACC-2001",
        "amount": "1500.00",
        "currency": "USD",
        "transaction_type": "transfer",
        "risk_score": 0,
        "risk_factors": [],
        "flagged": False,
        "status": "fraud_cleared",
    }
    base.update(overrides)
    return base


def test_settle_transaction_adds_status_and_timestamp():
    result = settlement.settle_transaction(_cleared_record())
    assert result["status"] == "settled"
    assert "settled_at" in result
    assert result["transaction_id"] == "TXN001"


def test_run_stage_writes_flat_settled_record(tmp_path):
    shared = tmp_path
    for sub in ("input", "processing", "output", "results"):
        (shared / sub).mkdir(parents=True)

    envelope = make_envelope("fraud_detector", "settlement", "transaction", _cleared_record())
    (shared / "output" / "TXN001.json").write_text(json.dumps(envelope))

    settlement.run_stage(shared_dir=shared)

    result_files = list((shared / "results").glob("*.json"))
    assert len(result_files) == 1
    record = json.loads(result_files[0].read_text())
    assert record["status"] == "settled"
    assert "settled_at" in record
    assert "data" not in record


def test_run_stage_ignores_envelopes_not_targeted_at_settlement(tmp_path):
    shared = tmp_path
    for sub in ("input", "processing", "output", "results"):
        (shared / sub).mkdir(parents=True)

    envelope = make_envelope("validator", "fraud_detector", "transaction", _cleared_record())
    (shared / "output" / "TXN001.json").write_text(json.dumps(envelope))

    settlement.run_stage(shared_dir=shared)

    assert not list((shared / "results").glob("*.json"))
