"""
test_import_json.py — Unit tests for JSON import parsing.

Tests the import_json() service function directly with raw bytes.

Coverage targets:
  src/services/import_service.py — import_json branch
"""

import json

import pytest

from src.services.import_service import import_json


# ── Helpers ────────────────────────────────────────────────────────────────────


VALID_TICKET = {
    "customer_id":    "cust-01",
    "customer_email": "alice@example.com",
    "customer_name":  "Alice Johnson",
    "subject":        "Cannot log into my account",
    "description":    "I have been unable to access my account since yesterday evening.",
    "category":       "account_access",
    "priority":       "urgent",
}


def to_bytes(data) -> bytes:
    return json.dumps(data).encode("utf-8")


# ── Bare array format ──────────────────────────────────────────────────────────


def test_import_json_bare_array():
    result = import_json(to_bytes([VALID_TICKET]))
    assert result.total == 1
    assert result.successful == 1
    assert result.tickets[0].customer_id == "cust-01"


def test_import_json_bare_array_multiple():
    ticket2 = {**VALID_TICKET, "customer_email": "bob@example.com", "customer_id": "c2"}
    result = import_json(to_bytes([VALID_TICKET, ticket2]))
    assert result.total == 2
    assert result.successful == 2


# ── Envelope format ────────────────────────────────────────────────────────────


def test_import_json_envelope_format():
    result = import_json(to_bytes({"tickets": [VALID_TICKET]}))
    assert result.total == 1
    assert result.successful == 1


def test_import_json_fixture_file():
    with open("tests/fixtures/valid_tickets.json", "rb") as f:
        content = f.read()
    result = import_json(content)
    assert result.successful == result.total
    assert result.failed == 0


# ── Error cases ────────────────────────────────────────────────────────────────


def test_import_json_malformed_json_raises():
    with pytest.raises(ValueError, match="Cannot parse JSON"):
        import_json(b"{ this is not valid json }")


def test_import_json_wrong_structure_raises():
    with pytest.raises(ValueError):
        import_json(to_bytes({"not_tickets": []}))


def test_import_json_envelope_tickets_not_array_raises():
    with pytest.raises(ValueError):
        import_json(to_bytes({"tickets": "should-be-array"}))


def test_import_json_empty_array_raises():
    with pytest.raises(ValueError, match="no ticket"):
        import_json(to_bytes([]))


def test_import_json_empty_envelope_raises():
    with pytest.raises(ValueError, match="no ticket"):
        import_json(to_bytes({"tickets": []}))


def test_import_json_partial_failure():
    bad_ticket = {**VALID_TICKET, "customer_email": "not-an-email", "customer_id": "c2"}
    result = import_json(to_bytes([VALID_TICKET, bad_ticket]))
    assert result.total == 2
    assert result.successful == 1
    assert result.failed == 1
    assert result.errors[0].row == 2


def test_import_json_with_tags_list():
    ticket = {**VALID_TICKET, "tags": ["billing", "refund"]}
    result = import_json(to_bytes([ticket]))
    assert result.tickets[0].tags == ["billing", "refund"]


def test_import_json_with_nested_metadata():
    ticket = {
        **VALID_TICKET,
        "metadata": {"source": "web_form", "device_type": "desktop"},
    }
    result = import_json(to_bytes([ticket]))
    assert result.tickets[0].metadata.source.value == "web_form"
