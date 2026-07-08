"""Simple Flask front-end for the transaction pipeline.

Shows the results currently in shared/results/ and lets the user trigger a
fresh pipeline run from the browser. Reads results only -- masks account
identifiers before rendering, per the PII rule in agents.md.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from flask import Flask, jsonify, render_template

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from pipeline.common import RESULTS_DIR, mask_account  # noqa: E402

app = Flask(__name__)


def _load_results() -> list[dict]:
    records = []
    for path in sorted(RESULTS_DIR.glob("*.json")):
        if path.name == "pipeline_summary.json":
            continue
        record = json.loads(path.read_text())
        record["source_account"] = mask_account(record.get("source_account"))
        record["destination_account"] = mask_account(record.get("destination_account"))
        records.append(record)
    return sorted(records, key=lambda r: r.get("transaction_id", ""))


def _load_summary() -> dict | None:
    summary_path = RESULTS_DIR / "pipeline_summary.json"
    if not summary_path.exists():
        return None
    return json.loads(summary_path.read_text())


@app.route("/")
def dashboard():
    return render_template("dashboard.html", results=_load_results(), summary=_load_summary())


@app.route("/api/results")
def api_results():
    return jsonify(_load_results())


@app.route("/api/summary")
def api_summary():
    return jsonify(_load_summary() or {})


@app.route("/api/run", methods=["POST"])
def api_run():
    proc = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "orchestrator.py")],
        cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=60,
    )
    return jsonify({
        "returncode": proc.returncode,
        "summary": _load_summary(),
    })


if __name__ == "__main__":
    # Port 5000 collides with macOS AirPlay Receiver on the IPv6 loopback
    # (localhost resolves to ::1 first), which returns a 403 before Flask
    # ever sees the request. 5050 avoids that entirely.
    app.run(debug=True, port=5050)
