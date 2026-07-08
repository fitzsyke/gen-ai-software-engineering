import json

from pipeline import fraud_detector
from pipeline.common import make_envelope


def _validated_record(**overrides):
    base = {
        "transaction_id": "TXN001",
        "timestamp": "2026-03-16T09:00:00Z",
        "source_account": "ACC-1001",
        "destination_account": "ACC-2001",
        "amount": "1500.00",
        "currency": "USD",
        "transaction_type": "transfer",
        "description": "Monthly rent payment",
        "metadata": {"channel": "online", "country": "US"},
        "valid": True,
        "reason": None,
    }
    base.update(overrides)
    return base


def test_ordinary_transaction_is_not_flagged():
    result = fraud_detector.score_transaction(_validated_record())
    assert result["flagged"] is False
    assert result["risk_score"] < 50
    assert result["risk_factors"] == []


def test_high_value_transaction_is_flagged():
    result = fraud_detector.score_transaction(_validated_record(amount="75000.00"))
    assert result["flagged"] is True
    assert "high_value" in result["risk_factors"]
    assert result["risk_score"] >= 50


def test_boundary_amount_just_under_threshold_is_not_high_value():
    result = fraud_detector.score_transaction(_validated_record(amount="9999.99"))
    assert "high_value" not in result["risk_factors"]
    assert result["flagged"] is False


def test_cross_border_and_off_hours_combination_is_flagged():
    result = fraud_detector.score_transaction(
        _validated_record(
            amount="500.00",
            currency="EUR",
            timestamp="2026-03-16T02:47:00Z",
            metadata={"channel": "api", "country": "DE"},
        )
    )
    assert result["flagged"] is True
    assert set(result["risk_factors"]) == {"cross_border", "off_hours"}
    assert result["risk_score"] == 60


def test_domestic_daytime_transaction_is_not_cross_border_or_off_hours():
    result = fraud_detector.score_transaction(
        _validated_record(timestamp="2026-03-16T14:00:00Z")
    )
    assert "cross_border" not in result["risk_factors"]
    assert "off_hours" not in result["risk_factors"]


def test_negative_refund_amount_scored_by_absolute_value():
    result = fraud_detector.score_transaction(
        _validated_record(amount="-100.00", currency="GBP", transaction_type="refund")
    )
    assert "high_value" not in result["risk_factors"]


def test_run_stage_writes_flat_terminal_record_for_flagged_transaction(tmp_path):
    shared = tmp_path
    for sub in ("input", "processing", "output", "results"):
        (shared / sub).mkdir(parents=True)

    envelope = make_envelope("validator", "fraud_detector", "transaction", _validated_record(amount="75000.00"))
    (shared / "output" / "TXN005.json").write_text(json.dumps(envelope))

    fraud_detector.run_stage(shared_dir=shared)

    result_files = list((shared / "results").glob("*.json"))
    assert len(result_files) == 1
    record = json.loads(result_files[0].read_text())
    assert record["status"] == "flagged"
    assert record["risk_score"] >= 50
    # Terminal record must be flat, not envelope-wrapped.
    assert "data" not in record


def test_run_stage_passes_through_cleared_transaction_to_output(tmp_path):
    shared = tmp_path
    for sub in ("input", "processing", "output", "results"):
        (shared / sub).mkdir(parents=True)

    envelope = make_envelope("validator", "fraud_detector", "transaction", _validated_record())
    (shared / "output" / "TXN001.json").write_text(json.dumps(envelope))

    fraud_detector.run_stage(shared_dir=shared)

    output_files = list((shared / "output").glob("*.json"))
    assert len(output_files) == 1
    out_envelope = json.loads(output_files[0].read_text())
    assert out_envelope["source_stage"] == "fraud_detector"
    assert out_envelope["target_stage"] == "settlement"
    assert not list((shared / "results").glob("*.json"))


def test_run_stage_ignores_envelopes_not_targeted_at_this_stage(tmp_path):
    shared = tmp_path
    for sub in ("input", "processing", "output", "results"):
        (shared / sub).mkdir(parents=True)

    envelope = make_envelope("fraud_detector", "settlement", "transaction", _validated_record())
    (shared / "output" / "TXN001.json").write_text(json.dumps(envelope))

    fraud_detector.run_stage(shared_dir=shared)

    # Untouched: still targeted at settlement, not re-processed by fraud_detector.
    remaining = json.loads((shared / "output" / "TXN001.json").read_text())
    assert remaining["target_stage"] == "settlement"
    assert not list((shared / "results").glob("*.json"))
