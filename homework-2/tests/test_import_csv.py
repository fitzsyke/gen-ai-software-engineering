"""
test_import_csv.py — Unit tests for CSV import parsing.

Tests the import_csv() service function directly with raw bytes,
not via the HTTP layer.

Coverage targets:
  src/services/import_service.py — import_csv + normalization helpers
"""

import pytest

from src.services.import_service import import_csv


# ── Helpers ────────────────────────────────────────────────────────────────────

VALID_HEADERS = (
    "customer_id,customer_email,customer_name,subject,description,"
    "category,priority"
)

def make_csv(*rows: str, headers: str = VALID_HEADERS) -> bytes:
    """Build CSV bytes from a header string and data row strings."""
    lines = [headers] + list(rows)
    return "\n".join(lines).encode("utf-8")


VALID_ROW = (
    'cust-01,alice@example.com,Alice Johnson,'
    '"Cannot log in","I have been unable to access my account since yesterday.",'
    'account_access,urgent'
)


# ── Success cases ──────────────────────────────────────────────────────────────


def test_import_csv_single_valid_row():
    result = import_csv(make_csv(VALID_ROW))
    assert result.total == 1
    assert result.successful == 1
    assert result.failed == 0
    assert result.tickets[0].customer_id == "cust-01"


def test_import_csv_fixture_file():
    with open("tests/fixtures/valid_tickets.csv", "rb") as f:
        content = f.read()
    result = import_csv(content)
    assert result.successful == result.total
    assert result.failed == 0


def test_import_csv_tags_comma_separated():
    headers = VALID_HEADERS + ",tags"
    row = VALID_ROW + ',"billing,refund"'
    result = import_csv(make_csv(row, headers=headers))
    assert result.successful == 1
    assert result.tickets[0].tags == ["billing", "refund"]


def test_import_csv_metadata_dot_notation():
    headers = VALID_HEADERS + ",metadata.source,metadata.device_type"
    row = VALID_ROW + ",web_form,desktop"
    result = import_csv(make_csv(row, headers=headers))
    assert result.successful == 1
    ticket = result.tickets[0]
    assert ticket.metadata.source.value == "web_form"
    assert ticket.metadata.device_type.value == "desktop"


def test_import_csv_empty_optional_fields_become_none():
    headers = VALID_HEADERS + ",assigned_to,metadata.device_type"
    row = VALID_ROW + ",,"  # both empty
    result = import_csv(make_csv(row, headers=headers))
    assert result.successful == 1
    assert result.tickets[0].assigned_to is None
    assert result.tickets[0].metadata.device_type is None


def test_import_csv_excel_bom():
    """UTF-8 BOM (added by Excel) must be handled silently."""
    bom = b"\xef\xbb\xbf"
    content = bom + make_csv(VALID_ROW)
    result = import_csv(content)
    assert result.successful == 1


# ── Failure cases ──────────────────────────────────────────────────────────────


def test_import_csv_empty_file_raises():
    with pytest.raises(ValueError, match="empty"):
        import_csv(b"customer_id,customer_email\n")  # headers only


def test_import_csv_invalid_email_row_fails():
    bad_row = VALID_ROW.replace("alice@example.com", "not-an-email")
    result = import_csv(make_csv(bad_row))
    assert result.failed == 1
    assert result.successful == 0
    assert result.errors[0].row == 1
    assert any("email" in e.lower() for e in result.errors[0].errors)


def test_import_csv_description_too_short_fails():
    bad_row = (
        'cust-01,alice@example.com,Alice,Subject,short,account_access,urgent'
    )
    result = import_csv(make_csv(bad_row))
    assert result.failed == 1


def test_import_csv_invalid_category_enum_fails():
    bad_row = VALID_ROW.replace("account_access", "not_a_category")
    result = import_csv(make_csv(bad_row))
    assert result.failed == 1


def test_import_csv_mixed_success_and_failure():
    bad_row = VALID_ROW.replace("alice@example.com", "bad-email")
    content = make_csv(VALID_ROW, bad_row)
    result = import_csv(content)
    assert result.total == 2
    assert result.successful == 1
    assert result.failed == 1


def test_import_csv_row_numbers_correct():
    bad_row = VALID_ROW.replace("alice@example.com", "bad-email")
    content = make_csv(VALID_ROW, bad_row)
    result = import_csv(content)
    # bad_row is the 2nd data row → row number 2
    assert result.errors[0].row == 2
