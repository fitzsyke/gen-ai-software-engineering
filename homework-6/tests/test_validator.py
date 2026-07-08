import json

from pipeline import validator
from pipeline.common import make_envelope


def _record(**overrides):
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
    }
    base.update(overrides)
    return base


def test_valid_transaction_passes():
    result = validator.validate_transaction(_record())
    assert result["valid"] is True
    assert result["reason"] is None


def test_missing_required_field_is_rejected():
    record = _record()
    del record["destination_account"]
    result = validator.validate_transaction(record)
    assert result["valid"] is False
    assert result["reason"] == "missing_field:destination_account"


def test_invalid_currency_is_rejected():
    result = validator.validate_transaction(_record(currency="XYZ"))
    assert result["valid"] is False
    assert result["reason"] == "invalid_currency"


def test_non_numeric_amount_is_rejected():
    result = validator.validate_transaction(_record(amount="not-a-number"))
    assert result["valid"] is False
    assert result["reason"] == "invalid_amount"


def test_negative_amount_on_refund_is_valid():
    result = validator.validate_transaction(
        _record(amount="-100.00", currency="GBP", transaction_type="refund")
    )
    assert result["valid"] is True


def test_negative_amount_on_non_refund_is_rejected():
    result = validator.validate_transaction(
        _record(amount="-100.00", transaction_type="transfer")
    )
    assert result["valid"] is False
    assert result["reason"] == "invalid_amount"


def test_high_value_transaction_still_valid_at_validation_stage():
    # Validation only checks well-formedness; fraud scoring happens later.
    result = validator.validate_transaction(_record(amount="75000.00"))
    assert result["valid"] is True


def test_boundary_amount_just_under_ten_thousand_is_valid():
    result = validator.validate_transaction(_record(amount="9999.99"))
    assert result["valid"] is True


def test_run_stage_routes_valid_transaction_to_output(tmp_path):
    shared = tmp_path
    for sub in ("input", "processing", "output", "results"):
        (shared / sub).mkdir(parents=True)

    envelope = make_envelope("orchestrator", "validator", "transaction", _record())
    (shared / "input" / "TXN001.json").write_text(json.dumps(envelope))

    validator.run_stage(shared_dir=shared)

    assert not (shared / "input" / "TXN001.json").exists()
    output_files = list((shared / "output").glob("*.json"))
    assert len(output_files) == 1
    out_envelope = json.loads(output_files[0].read_text())
    assert out_envelope["source_stage"] == "validator"
    assert out_envelope["target_stage"] == "fraud_detector"
    assert out_envelope["data"]["valid"] is True
    assert not list((shared / "results").glob("*.json"))


def test_run_stage_routes_invalid_transaction_to_results(tmp_path):
    shared = tmp_path
    for sub in ("input", "processing", "output", "results"):
        (shared / sub).mkdir(parents=True)

    envelope = make_envelope("orchestrator", "validator", "transaction", _record(currency="XYZ"))
    (shared / "input" / "TXN006.json").write_text(json.dumps(envelope))

    validator.run_stage(shared_dir=shared)

    result_files = list((shared / "results").glob("*.json"))
    assert len(result_files) == 1
    record = json.loads(result_files[0].read_text())
    assert record["status"] == "rejected"
    assert record["reason"] == "invalid_currency"
    assert not list((shared / "output").glob("*.json"))


def test_dry_run_reports_valid_and_invalid_counts(tmp_path, capsys):
    sample_file = tmp_path / "sample.json"
    sample_file.write_text(json.dumps([_record(), _record(transaction_id="TXN006", currency="XYZ")]))

    validator._dry_run(sample_file)

    captured = capsys.readouterr().out
    assert "Total: 2" in captured
    assert "Valid: 1" in captured
    assert "Invalid: 1" in captured
    assert "TXN006" in captured
    assert "invalid_currency" in captured
