"""Custom FastMCP server exposing the transaction pipeline's results as queryable
tools/resources for any MCP-aware client. Reads only from shared/results/ — it
never triggers pipeline runs itself.
"""
import json
from pathlib import Path

from fastmcp import FastMCP

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = PROJECT_ROOT / "shared" / "results"
SUMMARY_FILE = RESULTS_DIR / "pipeline_summary.json"

mcp = FastMCP("pipeline-status")


def _load_result_files() -> list[dict]:
    if not RESULTS_DIR.exists():
        return []
    results = []
    for path in sorted(RESULTS_DIR.glob("*.json")):
        if path.name == SUMMARY_FILE.name:
            continue
        try:
            results.append(json.loads(path.read_text()))
        except (json.JSONDecodeError, OSError):
            continue
    return results


@mcp.tool()
def get_transaction_status(transaction_id: str) -> dict:
    """Return the current pipeline status for a single transaction_id, read from shared/results/."""
    for record in _load_result_files():
        if record.get("transaction_id") == transaction_id:
            return record
    return {"transaction_id": transaction_id, "status": "not_found"}


@mcp.tool()
def list_pipeline_results() -> dict:
    """Return a summary of all processed transactions currently in shared/results/."""
    records = _load_result_files()
    counts: dict[str, int] = {}
    for record in records:
        status = record.get("status", "unknown")
        counts[status] = counts.get(status, 0) + 1
    return {
        "total": len(records),
        "counts_by_status": counts,
        "transactions": records,
    }


@mcp.resource("pipeline://summary")
def pipeline_summary() -> str:
    """Return the latest pipeline run summary as text."""
    if SUMMARY_FILE.exists():
        return SUMMARY_FILE.read_text()
    records = _load_result_files()
    if not records:
        return "No pipeline run has produced results yet. Run the pipeline first."
    counts: dict[str, int] = {}
    for record in records:
        status = record.get("status", "unknown")
        counts[status] = counts.get(status, 0) + 1
    return json.dumps({"total": len(records), "counts_by_status": counts}, indent=2)


if __name__ == "__main__":
    mcp.run()
