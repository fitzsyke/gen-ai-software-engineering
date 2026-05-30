"""
test_integration.py — End-to-end workflow tests.

Tests realistic multi-step workflows that cross service and storage boundaries.
Each test exercises the full stack: HTTP → Router → Service → Storage → Response.

Coverage targets:
  Interaction between ticket_service + import_service + classify_service
"""

import threading

import pytest
from starlette.testclient import TestClient


# ── Full ticket lifecycle ──────────────────────────────────────────────────────


def test_full_ticket_lifecycle(client: TestClient, sample_ticket: dict):
    """Create → Read → Update → Delete a ticket, verifying state at each step."""

    # 1. Create
    create_resp = client.post("/tickets", json=sample_ticket)
    assert create_resp.status_code == 201
    ticket = create_resp.json()
    ticket_id = ticket["id"]
    assert ticket["status"] == "new"

    # 2. Read — should match what was created
    get_resp = client.get(f"/tickets/{ticket_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == ticket_id

    # 3. Update — assign and start work
    update_resp = client.put(
        f"/tickets/{ticket_id}",
        json={"status": "in_progress", "assigned_to": "agent-sarah"},
    )
    assert update_resp.status_code == 200
    updated = update_resp.json()
    assert updated["status"] == "in_progress"
    assert updated["assigned_to"] == "agent-sarah"
    assert updated["resolved_at"] is None

    # 4. Resolve — should auto-stamp resolved_at
    resolve_resp = client.put(f"/tickets/{ticket_id}", json={"status": "resolved"})
    assert resolve_resp.status_code == 200
    assert resolve_resp.json()["resolved_at"] is not None

    # 5. Delete
    del_resp = client.delete(f"/tickets/{ticket_id}")
    assert del_resp.status_code == 204

    # 6. Confirm gone
    assert client.get(f"/tickets/{ticket_id}").status_code == 404


# ── Bulk import then filter ────────────────────────────────────────────────────


def test_bulk_csv_import_then_filter(client: TestClient):
    """Import 5 tickets from CSV, then verify filtering works on the result."""
    with open("tests/fixtures/valid_tickets.csv", "rb") as f:
        resp = client.post("/tickets/import", files={"file": ("t.csv", f, "text/csv")})
    assert resp.status_code == 201
    summary = resp.json()
    assert summary["successful"] == 5

    # Filter by category — should find only account_access tickets
    account_tickets = client.get("/tickets?category=account_access").json()
    assert len(account_tickets) >= 1
    for t in account_tickets:
        assert t["category"] == "account_access"

    # Filter by priority — should find only urgent tickets
    urgent_tickets = client.get("/tickets?priority=urgent").json()
    for t in urgent_tickets:
        assert t["priority"] == "urgent"


def test_all_three_formats_combined(client: TestClient):
    """Import CSV + JSON + XML and confirm ticket counts add up correctly."""
    files = [
        ("tests/fixtures/valid_tickets.csv", "t.csv", "text/csv"),
        ("tests/fixtures/valid_tickets.json", "t.json", "application/json"),
        ("tests/fixtures/valid_tickets.xml", "t.xml", "application/xml"),
    ]
    total_imported = 0
    for path, name, mime in files:
        with open(path, "rb") as f:
            resp = client.post("/tickets/import", files={"file": (name, f, mime)})
        body = resp.json()
        total_imported += body["successful"]

    all_tickets = client.get("/tickets").json()
    assert len(all_tickets) == total_imported


# ── Auto-classify workflow ─────────────────────────────────────────────────────


def test_auto_classify_on_creation_stores_result(client: TestClient, sample_ticket: dict):
    """Ticket created with auto_classify=True should have classification stored."""
    data = {**sample_ticket, "category": "other", "auto_classify": True}
    resp = client.post("/tickets", json=data)
    assert resp.status_code == 201
    ticket = resp.json()

    # Classification should be stored
    assert ticket["classification"] is not None
    # category should be overwritten from 'other'
    assert ticket["category"] != "other"

    # Retrieving the ticket should return same classification
    get_resp = client.get(f"/tickets/{ticket['id']}")
    stored = get_resp.json()
    assert stored["classification"] is not None
    assert stored["category"] == ticket["category"]


def test_auto_classify_then_manual_override(client: TestClient, sample_ticket: dict):
    """Auto-classify assigns a category, then a manual PUT overrides it."""
    ticket = client.post("/tickets", json=sample_ticket).json()
    ticket_id = ticket["id"]

    # Auto-classify
    classified = client.post(f"/tickets/{ticket_id}/auto-classify").json()
    assert classified["classification"] is not None

    # Manual override via PUT
    override_resp = client.put(f"/tickets/{ticket_id}", json={"category": "other", "priority": "low"})
    assert override_resp.status_code == 200
    overridden = override_resp.json()
    assert overridden["category"] == "other"
    assert overridden["priority"] == "low"
    # Classification result still stored (manual override doesn't clear it)
    assert overridden["classification"] is not None


def test_import_with_auto_classify_flag(client: TestClient):
    """JSON import rows with auto_classify=True should be classified."""
    import json

    tickets_data = {
        "tickets": [
            {
                "customer_id": "c1",
                "customer_email": "alice@example.com",
                "customer_name": "Alice",
                "subject": "Cannot log into my account",
                "description": "My password reset does not work and I am locked out of my account.",
                "category": "other",
                "priority": "low",
                "auto_classify": True,
            }
        ]
    }
    content = json.dumps(tickets_data).encode("utf-8")
    resp = client.post("/tickets/import", files={"file": ("t.json", content, "application/json")})
    assert resp.status_code == 201
    body = resp.json()
    assert body["successful"] == 1
    ticket = body["tickets"][0]
    assert ticket["category"] == "account_access"  # classifier should catch this
    assert ticket["classification"] is not None


# ── Concurrent request safety ─────────────────────────────────────────────────


def test_concurrent_creates_no_data_corruption(client: TestClient, sample_ticket: dict):
    """20 concurrent threads each create one ticket; store must hold exactly 20."""
    errors = []
    results = []

    def create_one(index: int):
        data = {
            **sample_ticket,
            "customer_email": f"user{index}@example.com",
            "customer_id": f"cust-{index}",
        }
        try:
            resp = client.post("/tickets", json=data)
            results.append(resp.status_code)
        except Exception as exc:
            errors.append(str(exc))

    threads = [threading.Thread(target=create_one, args=(i,)) for i in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == [], f"Thread errors: {errors}"
    assert all(s == 201 for s in results)
    all_tickets = client.get("/tickets").json()
    assert len(all_tickets) == 20
