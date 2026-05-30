"""
test_edge_cases.py — Targeted tests for remaining uncovered code paths.

Covers error branches, Unicode decode errors, all-failed imports,
store duplicate detection, and TicketUpdate validator edge cases.
"""

import pytest
from pydantic import ValidationError
from starlette.testclient import TestClient

from src.models.ticket import TicketUpdate
from src.services.import_service import import_csv, import_json, import_xml
from src.storage.ticket_store import store, TicketStore


# ── TicketUpdate validators with None input ───────────────────────────────────
# These validators return None immediately — cover those early-return branches.


def test_ticket_update_subject_none_passes():
    u = TicketUpdate(subject=None)
    assert u.subject is None


def test_ticket_update_subject_blank_raises():
    with pytest.raises(ValidationError):
        TicketUpdate(subject="   ")


def test_ticket_update_description_none_passes():
    u = TicketUpdate(description=None)
    assert u.description is None


def test_ticket_update_description_too_short_raises():
    with pytest.raises(ValidationError):
        TicketUpdate(description="short")


def test_ticket_update_description_too_long_raises():
    with pytest.raises(ValidationError):
        TicketUpdate(description="x" * 2001)


def test_ticket_update_tags_none_passes():
    u = TicketUpdate(tags=None)
    assert u.tags is None


def test_ticket_update_tags_strips_empties():
    u = TicketUpdate(tags=["  billing  ", "", "refund"])
    assert u.tags == ["billing", "refund"]


# ── TicketStore duplicate detection ──────────────────────────────────────────


def test_store_add_duplicate_raises():
    """Adding a ticket with an existing id must raise ValueError."""
    from src.models.ticket import Category, Priority, Status, Ticket, TicketMetadata
    from datetime import datetime, timezone
    from uuid import uuid4

    now = datetime.now(timezone.utc)
    ticket = Ticket(
        id=uuid4(),
        customer_id="c1",
        customer_email="a@b.com",
        customer_name="Alice",
        subject="Test",
        description="Long enough description for test.",
        category=Category.other,
        priority=Priority.low,
        status=Status.new,
        created_at=now,
        updated_at=now,
    )
    store.add(ticket)
    with pytest.raises(ValueError, match="already exists"):
        store.add(ticket)


def test_store_update_nonexistent_returns_none():
    result = store.update("nonexistent-id", None)
    assert result is None


def test_store_clear_empties_store():
    store.clear()
    assert store.count() == 0


# ── Import: all rows fail → still 201 ────────────────────────────────────────


def test_import_json_all_rows_fail_returns_201(client: TestClient):
    """When every row fails, status is still 201 (error details in body)."""
    import json
    bad_tickets = {
        "tickets": [
            {
                "customer_id": "c1",
                "customer_email": "bad-email",
                "customer_name": "Alice",
                "subject": "Test",
                "description": "Long enough description here.",
                "category": "other",
                "priority": "low",
            },
            {
                "customer_id": "   ",  # blank
                "customer_email": "bob@example.com",
                "customer_name": "Bob",
                "subject": "Test",
                "description": "Long enough description here.",
                "category": "other",
                "priority": "low",
            },
        ]
    }
    content = json.dumps(bad_tickets).encode()
    resp = client.post("/tickets/import", files={"file": ("t.json", content, "application/json")})
    # All rows failed → code falls through to status_code = 201
    assert resp.status_code == 201
    body = resp.json()
    assert body["successful"] == 0
    assert body["failed"] == 2


# ── Import: malformed file → 400 ──────────────────────────────────────────────


def test_import_malformed_xml_returns_400(client: TestClient):
    bad_xml = b"<tickets><ticket>unclosed</tickets>"
    resp = client.post("/tickets/import", files={"file": ("t.xml", bad_xml, "application/xml")})
    assert resp.status_code == 400


def test_import_malformed_json_returns_400(client: TestClient):
    resp = client.post("/tickets/import", files={"file": ("t.json", b"{bad json}", "application/json")})
    assert resp.status_code == 400


def test_import_empty_csv_returns_400(client: TestClient):
    resp = client.post("/tickets/import", files={"file": ("t.csv", b"customer_id,customer_email\n", "text/csv")})
    assert resp.status_code == 400


# ── Import: UnicodeDecodeError ────────────────────────────────────────────────


def test_import_csv_bad_encoding_raises():
    bad_bytes = b"\xff\xfe" + b"invalid utf8 content \x80\x81"
    with pytest.raises(ValueError, match="encoding"):
        import_csv(bad_bytes)


def test_import_json_bad_encoding_raises():
    with pytest.raises(ValueError, match="encoding"):
        import_json(b"\xff\xfe\x00invalid")


def test_import_xml_bad_encoding_raises():
    with pytest.raises(ValueError):
        import_xml(b"\xff\xfe" + b"<tickets>\x80\x81</tickets>")


# ── Import: normalize_empty_strings recursive dict ────────────────────────────


def test_import_csv_nested_empty_metadata_normalized():
    """
    When a CSV row has metadata.source="" (empty), normalization should
    convert it to None so Pydantic uses the default (Source.api).
    """
    headers = (
        "customer_id,customer_email,customer_name,subject,description,"
        "category,priority,metadata.source"
    )
    row = "c1,alice@example.com,Alice,Cannot log in,I have been unable to access my account since yesterday.,account_access,urgent,"
    content = f"{headers}\n{row}".encode("utf-8")
    result = import_csv(content)
    assert result.successful == 1
    # Empty metadata.source → None → Pydantic uses default Source.api
    assert result.tickets[0].metadata.source.value == "api"


# ── XML: single <ticket> root element ────────────────────────────────────────


def test_import_xml_single_ticket_root():
    """XML with a single <ticket> as root (no wrapping <tickets>) must work."""
    xml = b"""
    <ticket>
      <customer_id>c1</customer_id>
      <customer_email>alice@example.com</customer_email>
      <customer_name>Alice</customer_name>
      <subject>Test ticket</subject>
      <description>I have been unable to access my account since yesterday evening.</description>
      <category>account_access</category>
      <priority>urgent</priority>
    </ticket>
    """
    result = import_xml(xml)
    assert result.total == 1
    assert result.successful == 1
