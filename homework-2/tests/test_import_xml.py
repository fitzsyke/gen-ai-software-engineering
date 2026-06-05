"""
test_import_xml.py — Unit tests for XML import parsing.

Tests the import_xml() service function directly with raw bytes.

Coverage targets:
  src/services/import_service.py — import_xml + _xml_element_to_dict
"""

import pytest

from src.services.import_service import import_xml


# ── Helpers ────────────────────────────────────────────────────────────────────


def make_xml(*ticket_blocks: str) -> bytes:
    """Wrap one or more <ticket>…</ticket> blocks in a <tickets> root."""
    inner = "\n".join(ticket_blocks)
    return f"<tickets>{inner}</tickets>".encode("utf-8")


VALID_TICKET_XML = """
<ticket>
  <customer_id>cust-x01</customer_id>
  <customer_email>alice@example.com</customer_email>
  <customer_name>Alice Johnson</customer_name>
  <subject>Cannot log into my account</subject>
  <description>I have been unable to access my account since yesterday evening.</description>
  <category>account_access</category>
  <priority>urgent</priority>
</ticket>
"""


# ── Success cases ──────────────────────────────────────────────────────────────


def test_import_xml_single_valid_ticket():
    result = import_xml(make_xml(VALID_TICKET_XML))
    assert result.total == 1
    assert result.successful == 1
    assert result.tickets[0].customer_id == "cust-x01"


def test_import_xml_fixture_file():
    with open("tests/fixtures/valid_tickets.xml", "rb") as f:
        content = f.read()
    result = import_xml(content)
    assert result.successful == result.total
    assert result.failed == 0


def test_import_xml_tags_repeated_elements():
    ticket = """
    <ticket>
      <customer_id>c1</customer_id>
      <customer_email>alice@example.com</customer_email>
      <customer_name>Alice</customer_name>
      <subject>Test ticket</subject>
      <description>I have been unable to access my account since yesterday evening.</description>
      <category>other</category>
      <priority>low</priority>
      <tags><tag>billing</tag><tag>refund</tag></tags>
    </ticket>
    """
    result = import_xml(make_xml(ticket))
    assert result.successful == 1
    assert result.tickets[0].tags == ["billing", "refund"]


def test_import_xml_tags_comma_string():
    ticket = """
    <ticket>
      <customer_id>c1</customer_id>
      <customer_email>alice@example.com</customer_email>
      <customer_name>Alice</customer_name>
      <subject>Test ticket</subject>
      <description>I have been unable to access my account since yesterday evening.</description>
      <category>other</category>
      <priority>low</priority>
      <tags>billing,refund</tags>
    </ticket>
    """
    result = import_xml(make_xml(ticket))
    assert result.successful == 1
    assert result.tickets[0].tags == ["billing", "refund"]


def test_import_xml_nested_metadata():
    ticket = """
    <ticket>
      <customer_id>c1</customer_id>
      <customer_email>alice@example.com</customer_email>
      <customer_name>Alice</customer_name>
      <subject>Test ticket</subject>
      <description>I have been unable to access my account since yesterday evening.</description>
      <category>other</category>
      <priority>low</priority>
      <metadata>
        <source>web_form</source>
        <device_type>desktop</device_type>
      </metadata>
    </ticket>
    """
    result = import_xml(make_xml(ticket))
    assert result.successful == 1
    ticket_obj = result.tickets[0]
    assert ticket_obj.metadata.source.value == "web_form"
    assert ticket_obj.metadata.device_type.value == "desktop"


def test_import_xml_multiple_tickets():
    result = import_xml(make_xml(VALID_TICKET_XML, VALID_TICKET_XML.replace("cust-x01", "cust-x02").replace("alice@example.com", "bob@example.com")))
    assert result.total == 2
    assert result.successful == 2


# ── Failure cases ──────────────────────────────────────────────────────────────


def test_import_xml_malformed_raises():
    with pytest.raises(ValueError, match="Cannot parse XML"):
        import_xml(b"<tickets><ticket>unclosed</tickets>")


def test_import_xml_no_ticket_elements_raises():
    with pytest.raises(ValueError, match="no <ticket>"):
        import_xml(b"<tickets><item>wrong</item></tickets>")


def test_import_xml_invalid_email_fails():
    bad = VALID_TICKET_XML.replace("alice@example.com", "not-an-email")
    result = import_xml(make_xml(bad))
    assert result.failed == 1
    assert result.successful == 0


def test_import_xml_mixed_success_failure():
    bad = VALID_TICKET_XML.replace("alice@example.com", "not-an-email")
    good = VALID_TICKET_XML.replace("cust-x01", "cust-x02").replace("alice@example.com", "bob@example.com")
    result = import_xml(make_xml(bad, good))
    assert result.total == 2
    assert result.successful == 1
    assert result.failed == 1
