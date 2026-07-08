# How to Run

## 1. Environment Setup

Requires Python 3.12+.

```bash
cd homework-6
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## 2. Run the Pipeline

```bash
python orchestrator.py
```

This loads `sample-transactions.json`, runs the validator → fraud detector → settlement stages in sequence, and writes one terminal record per transaction to `shared/results/`, plus a `shared/results/pipeline_summary.json` report. A summary also prints to stdout.

To validate transactions only, without running the full pipeline:

```bash
python -m pipeline.validator --dry-run sample-transactions.json
```

## 3. Run the Front-End

```bash
python frontend/app.py
```

Open `http://127.0.0.1:5050` in a browser. The dashboard shows the latest `shared/results/` contents and has a "Run Pipeline" button that re-runs the pipeline and refreshes the page.

(Port 5050 is used instead of the Flask default 5000 because macOS AirPlay Receiver also listens on port 5000 over IPv6 and will intercept `localhost` requests with an unrelated 403 before they reach Flask.)

## 4. Run the Tests and View Coverage

```bash
pytest --cov=pipeline --cov=orchestrator --cov-report=term-missing
```

Coverage must be ≥ 80% (hard gate enforced by the pre-push hook below); current coverage is 94%.

## 5. Coverage Gate Hook

`.claude/hooks/check-coverage.sh` runs automatically before any `git push` (configured in `.claude/settings.json` as a `PreToolUse` hook on `Bash`). It runs the full test suite with `--cov-fail-under=80` and blocks the push if coverage drops below 80% or any test fails. No manual step needed — it fires whenever Claude Code (or you, via the same hook) attempts `git push`.

## 6. MCP Server and Skills

Both MCP servers are configured in `mcp.json`:
- `context7` — library documentation lookup (used during code generation; see `research-notes.md`)
- `pipeline-status` — custom FastMCP server (`mcp/server.py`) exposing:
  - Tool `get_transaction_status(transaction_id)` — current status of one transaction from `shared/results/`
  - Tool `list_pipeline_results()` — summary of all processed transactions
  - Resource `pipeline://summary` — latest pipeline run summary as text

To run the custom MCP server standalone (e.g. for manual testing outside an MCP client):

```bash
python mcp/server.py
```

Two Claude Code slash commands wrap the common workflows:
- `/run-pipeline` — clears `shared/`, runs the full pipeline, and reports a results summary
- `/validate-transactions` — runs validation only (dry-run) and reports valid/invalid counts with reasons
