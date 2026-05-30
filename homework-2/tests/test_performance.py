"""
test_performance.py — Performance benchmark tests.

Verifies that individual operations complete within acceptable time budgets.
These are sanity checks for the in-memory implementation — not load tests.

Thresholds are generous to avoid flakiness on slow CI machines.
"""

import json
import threading
import time

import pytest
from starlette.testclient import TestClient


# ── Helpers ────────────────────────────────────────────────────────────────────


def elapsed(fn) -> float:
    """Return the wall-clock time (seconds) for a single function call."""
    start = time.perf_counter()
    fn()
    return time.perf_counter() - start


SAMPLE_TICKET = {
    "customer_id":    "perf-001",
    "customer_email": "perf@example.com",
    "customer_name":  "Perf User",
    "subject":        "Performance test ticket",
    "description":    "This ticket is created as part of a performance benchmark test.",
    "category":       "other",
    "priority":       "low",
}


# ── Single-operation benchmarks ────────────────────────────────────────────────


def test_create_ticket_under_100ms(client: TestClient):
    """Single ticket creation must complete in under 100 ms."""
    def create():
        resp = client.post("/tickets", json=SAMPLE_TICKET)
        assert resp.status_code == 201

    assert elapsed(create) < 0.1, "create_ticket exceeded 100 ms"


def test_get_ticket_under_50ms(client: TestClient):
    """Single ticket retrieval must complete in under 50 ms."""
    ticket_id = client.post("/tickets", json=SAMPLE_TICKET).json()["id"]

    def get():
        resp = client.get(f"/tickets/{ticket_id}")
        assert resp.status_code == 200

    assert elapsed(get) < 0.05, "get_ticket exceeded 50 ms"


def test_list_100_tickets_under_200ms(client: TestClient):
    """Listing 100 tickets must complete in under 200 ms."""
    for i in range(100):
        client.post("/tickets", json={**SAMPLE_TICKET, "customer_email": f"u{i}@example.com", "customer_id": f"c{i}"})

    def list_all():
        resp = client.get("/tickets")
        assert resp.status_code == 200
        assert len(resp.json()) == 100

    assert elapsed(list_all) < 0.2, "list_tickets (100 items) exceeded 200 ms"


def test_csv_import_15_rows_under_300ms(client: TestClient):
    """Importing the 15-row demo CSV must complete in under 300 ms."""
    with open("tests/fixtures/valid_tickets.csv", "rb") as f:
        content = f.read()

    def do_import():
        resp = client.post("/tickets/import", files={"file": ("t.csv", content, "text/csv")})
        assert resp.status_code == 201

    assert elapsed(do_import) < 0.3, "CSV import (5 rows) exceeded 300 ms"


def test_auto_classify_under_50ms(client: TestClient):
    """Auto-classification of a single ticket must complete in under 50 ms."""
    from src.services.classify_service import classify

    def do_classify():
        classify(
            "Cannot log into my account",
            "I forgot my password and the reset is not working. I have been locked out.",
        )

    assert elapsed(do_classify) < 0.05, "classify() exceeded 50 ms"


# ── Throughput tests ───────────────────────────────────────────────────────────


def test_20_sequential_creates_under_1s(client: TestClient):
    """20 sequential ticket creates must all complete in under 1 second total."""
    start = time.perf_counter()
    for i in range(20):
        resp = client.post("/tickets", json={**SAMPLE_TICKET, "customer_email": f"u{i}@perf.com", "customer_id": f"p{i}"})
        assert resp.status_code == 201
    duration = time.perf_counter() - start
    assert duration < 1.0, f"20 sequential creates took {duration:.2f}s (limit: 1.0s)"


def test_concurrent_20_requests_no_errors(client: TestClient):
    """20 concurrent creates — all must succeed with no race conditions."""
    errors = []
    statuses = []

    def create(i: int):
        try:
            resp = client.post("/tickets", json={
                **SAMPLE_TICKET,
                "customer_email": f"concurrent{i}@test.com",
                "customer_id": f"cc-{i}",
            })
            statuses.append(resp.status_code)
        except Exception as e:
            errors.append(str(e))

    threads = [threading.Thread(target=create, args=(i,)) for i in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors
    assert all(s == 201 for s in statuses)
    assert len(client.get("/tickets").json()) == 20
