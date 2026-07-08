import json
import shutil

import orchestrator
from pipeline.common import PROJECT_ROOT


def test_full_pipeline_run_against_sample_transactions(tmp_path):
    sample_copy = tmp_path / "sample-transactions.json"
    shutil.copy(PROJECT_ROOT / "sample-transactions.json", sample_copy)
    shared_dir = tmp_path / "shared"

    summary = orchestrator.run_pipeline(sample_file=sample_copy, shared_dir=shared_dir)

    assert summary["total"] == 8
    assert summary["counts_by_status"]["rejected"] == 1
    assert summary["counts_by_status"]["flagged"] == 3
    assert summary["counts_by_status"]["settled"] == 4

    rejected_ids = {r["transaction_id"] for r in summary["rejected"]}
    flagged_ids = {f["transaction_id"] for f in summary["flagged"]}
    assert rejected_ids == {"TXN006"}
    assert flagged_ids == {"TXN002", "TXN004", "TXN005"}

    # Every input transaction has exactly one terminal record in shared/results/.
    result_files = [
        p for p in (shared_dir / "results").glob("*.json") if p.name != "pipeline_summary.json"
    ]
    assert len(result_files) == 8

    # Intermediate directories are fully drained -- no leftover in-flight envelopes.
    assert not list((shared_dir / "input").glob("*.json"))
    assert not list((shared_dir / "output").glob("*.json"))
    assert not list((shared_dir / "processing").glob("*.json"))

    for path in result_files:
        record = json.loads(path.read_text())
        assert record["status"] in ("settled", "flagged", "rejected")
        assert "data" not in record  # flat terminal record, not envelope-wrapped


def test_rerunning_pipeline_skips_existing_summary_file(tmp_path):
    sample_copy = tmp_path / "sample-transactions.json"
    shutil.copy(PROJECT_ROOT / "sample-transactions.json", sample_copy)
    shared_dir = tmp_path / "shared"

    orchestrator.run_pipeline(sample_file=sample_copy, shared_dir=shared_dir)
    second_summary = orchestrator.run_pipeline(sample_file=sample_copy, shared_dir=shared_dir)

    # pipeline_summary.json from the first run must not be miscounted as a transaction.
    assert second_summary["total"] == 8


def test_pipeline_never_touches_real_shared_directory(tmp_path):
    real_results = PROJECT_ROOT / "shared" / "results"
    before = set(real_results.glob("*.json"))

    sample_copy = tmp_path / "sample-transactions.json"
    shutil.copy(PROJECT_ROOT / "sample-transactions.json", sample_copy)
    orchestrator.run_pipeline(sample_file=sample_copy, shared_dir=tmp_path / "shared")

    after = set(real_results.glob("*.json"))
    assert before == after
