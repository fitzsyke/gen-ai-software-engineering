"""
test_ticket_api.py — Integration tests for all HTTP endpoints.

Tests the full HTTP layer: request parsing, status codes, response shapes,
and error handling. The FastAPI TestClient talks to the real app with a
fresh in-memory store for each test (via the reset_store autouse fixture).

Coverage targets:
  src/routers/tickets.py   — all route handlers
  src/main.py              — health endpoint, global exception handler
"""

import pytest
from starlette.testclient import TestClient


# ── Health endpoint ────────────────────────────────────────────────────────────


def test_health_returns_ok(client: TestClient):
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["ticket_count"] == 0
    assert "version" in body


def test_health_ticket_count_increments(client: TestClient, sample_ticket: dict):
    client.post("/tickets", json=sample_ticket)
    resp = client.get("/health")
    assert resp.json()["ticket_count"] == 1


# ── POST /tickets ──────────────────────────────────────────────────────────────


def test_create_ticket_returns_201(client: TestClient, sample_ticket: dict):
    resp = client.post("/tickets", json=sample_ticket)
    assert resp.status_code == 201


def test_create_ticket_response_shape(client: TestClient, sample_ticket: dict):
    resp = client.post("/tickets", json=sample_ticket)
    body = resp.json()
    assert "id" in body
    assert "status" in body
    assert "created_at" in body
    assert "updated_at" in body
    assert body["status"] == "new"
    assert body["category"] == sample_ticket["category"]
    assert body["priority"] == sample_ticket["priority"]
    assert body["classification"] is None  # no auto_classify


def test_create_ticket_auto_classify_flag(client: TestClient, sample_ticket: dict):
    data = {**sample_ticket, "category": "other", "priority": "low", "auto_classify": True}
    resp = client.post("/tickets", json=data)
    assert resp.status_code == 201
    body = resp.json()
    # Classifier should override the submitted 'other' category
    assert body["category"] == "account_access"
    assert body["classification"] is not None
    cl = body["classification"]
    assert 0.0 <= cl["category_confidence"] <= 1.0
    assert 0.0 <= cl["priority_confidence"] <= 1.0
    assert isinstance(cl["matched_keywords"], list)


def test_create_ticket_invalid_email(client: TestClient, sample_ticket: dict):
    sample_ticket["customer_email"] = "not-an-email"
    resp = client.post("/tickets", json=sample_ticket)
    assert resp.status_code == 422


def test_create_ticket_description_too_short(client: TestClient, sample_ticket: dict):
    sample_ticket["description"] = "short"
    resp = client.post("/tickets", json=sample_ticket)
    assert resp.status_code == 422
    errors = resp.json()["detail"]
    assert any("description" in str(e) for e in errors)


def test_create_ticket_subject_blank(client: TestClient, sample_ticket: dict):
    sample_ticket["subject"] = "   "
    resp = client.post("/tickets", json=sample_ticket)
    assert resp.status_code == 422


def test_create_ticket_invalid_category_enum(client: TestClient, sample_ticket: dict):
    sample_ticket["category"] = "not_a_real_category"
    resp = client.post("/tickets", json=sample_ticket)
    assert resp.status_code == 422


def test_create_ticket_with_tags_and_metadata(client: TestClient, sample_ticket: dict):
    sample_ticket["tags"] = ["account", "security"]
    sample_ticket["metadata"] = {"source": "web_form", "device_type": "desktop"}
    resp = client.post("/tickets", json=sample_ticket)
    assert resp.status_code == 201
    body = resp.json()
    assert body["tags"] == ["account", "security"]
    assert body["metadata"]["source"] == "web_form"
    assert body["metadata"]["device_type"] == "desktop"


# ── GET /tickets/{id} ─────────────────────────────────────────────────────────


def test_get_ticket_success(client: TestClient, created_ticket: dict):
    ticket_id = created_ticket["id"]
    resp = client.get(f"/tickets/{ticket_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == ticket_id


def test_get_ticket_not_found(client: TestClient):
    resp = client.get("/tickets/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


def test_get_ticket_invalid_uuid(client: TestClient):
    resp = client.get("/tickets/not-a-uuid")
    assert resp.status_code == 422


# ── GET /tickets ──────────────────────────────────────────────────────────────


def test_list_tickets_empty(client: TestClient):
    resp = client.get("/tickets")
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_tickets_returns_all(client: TestClient, sample_ticket: dict):
    client.post("/tickets", json=sample_ticket)
    client.post("/tickets", json={**sample_ticket, "customer_email": "b@b.com"})
    resp = client.get("/tickets")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_list_tickets_filter_by_priority(client: TestClient, sample_ticket: dict):
    client.post("/tickets", json=sample_ticket)  # urgent
    client.post("/tickets", json={**sample_ticket, "customer_email": "b@b.com", "priority": "low"})
    resp = client.get("/tickets?priority=urgent")
    assert resp.status_code == 200
    tickets = resp.json()
    assert len(tickets) == 1
    assert tickets[0]["priority"] == "urgent"


def test_list_tickets_filter_by_status(client: TestClient, sample_ticket: dict):
    client.post("/tickets", json=sample_ticket)
    resp = client.get("/tickets?status=new")
    assert len(resp.json()) == 1
    resp2 = client.get("/tickets?status=resolved")
    assert resp2.json() == []


def test_list_tickets_filter_by_category(client: TestClient, sample_ticket: dict):
    client.post("/tickets", json=sample_ticket)  # account_access
    client.post("/tickets", json={**sample_ticket, "customer_email": "b@b.com", "category": "billing_question"})
    resp = client.get("/tickets?category=billing_question")
    assert len(resp.json()) == 1


def test_list_tickets_filter_by_tags(client: TestClient, sample_ticket: dict):
    client.post("/tickets", json={**sample_ticket, "tags": ["billing", "refund"]})
    client.post("/tickets", json={**sample_ticket, "customer_email": "b@b.com", "tags": ["account"]})
    resp = client.get("/tickets?tags=billing,refund")
    assert len(resp.json()) == 1


def test_list_tickets_filter_by_assigned_to(client: TestClient, sample_ticket: dict):
    client.post("/tickets", json={**sample_ticket, "assigned_to": "agent-sarah"})
    client.post("/tickets", json={**sample_ticket, "customer_email": "b@b.com"})
    resp = client.get("/tickets?assigned_to=agent-sarah")
    assert len(resp.json()) == 1


def test_list_tickets_invalid_enum_filter(client: TestClient):
    resp = client.get("/tickets?priority=super_urgent")
    assert resp.status_code == 422


def test_list_tickets_newest_first(client: TestClient, sample_ticket: dict):
    r1 = client.post("/tickets", json=sample_ticket).json()
    r2 = client.post("/tickets", json={**sample_ticket, "customer_email": "b@b.com"}).json()
    tickets = client.get("/tickets").json()
    # Second ticket created last → should be first in result
    assert tickets[0]["id"] == r2["id"]
    assert tickets[1]["id"] == r1["id"]


# ── PUT /tickets/{id} ─────────────────────────────────────────────────────────


def test_update_ticket_partial(client: TestClient, created_ticket: dict):
    ticket_id = created_ticket["id"]
    resp = client.put(f"/tickets/{ticket_id}", json={"priority": "low", "assigned_to": "agent-bob"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["priority"] == "low"
    assert body["assigned_to"] == "agent-bob"
    # Unchanged fields preserved
    assert body["category"] == created_ticket["category"]


def test_update_ticket_resolved_at_stamped(client: TestClient, created_ticket: dict):
    ticket_id = created_ticket["id"]
    assert created_ticket["resolved_at"] is None
    resp = client.put(f"/tickets/{ticket_id}", json={"status": "resolved"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "resolved"
    assert body["resolved_at"] is not None


def test_update_ticket_not_found(client: TestClient):
    resp = client.put(
        "/tickets/00000000-0000-0000-0000-000000000000",
        json={"priority": "low"},
    )
    assert resp.status_code == 404


# ── DELETE /tickets/{id} ──────────────────────────────────────────────────────


def test_delete_ticket_returns_204(client: TestClient, created_ticket: dict):
    ticket_id = created_ticket["id"]
    resp = client.delete(f"/tickets/{ticket_id}")
    assert resp.status_code == 204
    assert resp.content == b""


def test_delete_ticket_then_get_returns_404(client: TestClient, created_ticket: dict):
    ticket_id = created_ticket["id"]
    client.delete(f"/tickets/{ticket_id}")
    resp = client.get(f"/tickets/{ticket_id}")
    assert resp.status_code == 404


def test_delete_ticket_not_found(client: TestClient):
    resp = client.delete("/tickets/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


# ── POST /tickets/{id}/auto-classify ──────────────────────────────────────────


def test_auto_classify_endpoint_success(client: TestClient, created_ticket: dict):
    ticket_id = created_ticket["id"]
    resp = client.post(f"/tickets/{ticket_id}/auto-classify")
    assert resp.status_code == 200
    body = resp.json()
    assert body["classification"] is not None
    cl = body["classification"]
    assert cl["category"] in [
        "account_access", "technical_issue", "billing_question",
        "feature_request", "bug_report", "other",
    ]
    assert 0.0 <= cl["category_confidence"] <= 1.0
    assert "classified_at" in cl


def test_auto_classify_updates_category_and_priority(client: TestClient, sample_ticket: dict):
    # Submit with wrong category, expect classifier to fix it
    data = {**sample_ticket, "category": "other"}
    ticket_id = client.post("/tickets", json=data).json()["id"]
    resp = client.post(f"/tickets/{ticket_id}/auto-classify")
    body = resp.json()
    assert body["category"] == "account_access"


def test_auto_classify_endpoint_not_found(client: TestClient):
    resp = client.post("/tickets/00000000-0000-0000-0000-000000000000/auto-classify")
    assert resp.status_code == 404


def test_auto_classify_re_classify(client: TestClient, created_ticket: dict):
    """Calling auto-classify twice replaces the previous result."""
    ticket_id = created_ticket["id"]
    r1 = client.post(f"/tickets/{ticket_id}/auto-classify").json()
    r2 = client.post(f"/tickets/{ticket_id}/auto-classify").json()
    # Both should have classification; the second replaces the first
    assert r1["classification"] is not None
    assert r2["classification"] is not None
    # classified_at should differ (re-run)
    assert r2["classification"]["classified_at"] >= r1["classification"]["classified_at"]


# ── POST /tickets/import ──────────────────────────────────────────────────────


def test_import_unsupported_file_type(client: TestClient):
    resp = client.post(
        "/tickets/import",
        files={"file": ("tickets.txt", b"hello", "text/plain")},
    )
    assert resp.status_code == 415


def test_import_csv_all_success(client: TestClient):
    with open("tests/fixtures/valid_tickets.csv", "rb") as f:
        resp = client.post("/tickets/import", files={"file": ("tickets.csv", f, "text/csv")})
    assert resp.status_code == 201
    body = resp.json()
    assert body["successful"] == body["total"]
    assert body["failed"] == 0


def test_import_json_partial_failure(client: TestClient):
    with open("tests/fixtures/invalid_tickets.json", "rb") as f:
        resp = client.post("/tickets/import", files={"file": ("t.json", f, "application/json")})
    body = resp.json()
    assert body["failed"] > 0
    assert len(body["errors"]) > 0
    assert "row" in body["errors"][0]
