"""
import_service.py — Multi-format ticket bulk import logic.

Supports three file formats: CSV, JSON, and XML.

All three parsers follow the same pattern:
  1. Parse the raw file bytes into a list of plain Python dicts.
  2. Normalize format-specific quirks (BOM, flat metadata keys, tag strings).
  3. Pass every row through _validate_and_create_row(), which runs Pydantic
     validation and either creates the ticket or records the error.
  4. Return an ImportSummary with counts and per-row error details.

Public functions:
  import_csv(content: bytes)  → ImportSummary
  import_json(content: bytes) → ImportSummary
  import_xml(content: bytes)  → ImportSummary

Each raises ValueError with a human-readable message if the file itself is
malformed (unparseable), so the router can return a clean 400 response.
"""

import csv
import io
import json
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional, Tuple

from pydantic import ValidationError

from ..models.ticket import ImportError, ImportSummary, Ticket, TicketCreate
from .ticket_service import create_ticket


# ── Core validation helper ─────────────────────────────────────────────────────


def _validate_and_create_row(
    row: Dict[str, Any], row_number: int
) -> Tuple[Optional[Ticket], Optional[ImportError]]:
    """
    Try to build a TicketCreate from a raw dict and persist it.

    On success : returns (Ticket, None)
    On failure : returns (None, ImportError) with human-readable error messages

    All format-specific normalization should happen *before* calling this
    function so the Pydantic models don't need to know about file formats.
    """
    try:
        ticket_data = TicketCreate(**row)
        ticket = create_ticket(ticket_data)
        return ticket, None

    except ValidationError as exc:
        # Convert Pydantic's structured errors into plain strings for the response.
        error_messages = [
            f"{'.'.join(str(loc) for loc in err['loc'])}: {err['msg']}"
            for err in exc.errors()
        ]
        return None, ImportError(row=row_number, raw_data=row, errors=error_messages)

    except Exception as exc:
        # Catch unexpected errors (e.g. store errors) so one bad row doesn't
        # abort the entire import.
        return None, ImportError(row=row_number, raw_data=row, errors=[str(exc)])


# ── Normalization helpers ──────────────────────────────────────────────────────


def _normalize_tags(row: Dict[str, Any]) -> None:
    """
    Convert a comma-separated tags string (or None) to a list, in-place.

    CSV and XML files often represent arrays as comma-separated strings.
    Examples:
      "billing,refund"  → ["billing", "refund"]
      ""  or None       → []   (missing tags = empty list, not null)

    If tags is already a list, it is left unchanged.
    """
    tags_value = row.get("tags")
    if tags_value is None or tags_value == "":
        row["tags"] = []
    elif isinstance(tags_value, str):
        row["tags"] = [t.strip() for t in tags_value.split(",") if t.strip()]


def _normalize_metadata(row: Dict[str, Any]) -> None:
    """
    Handle flat metadata keys from CSV headers, in-place.

    CSV headers can't nest, so metadata fields are written as:
      metadata.source, metadata.browser, metadata.device_type

    This function collects those flat keys into a nested dict so Pydantic
    can validate them as a TicketMetadata object.

    Example input row keys: {"metadata.source": "web_form", "metadata.device_type": "desktop"}
    Example output:         {"metadata": {"source": "web_form", "device_type": "desktop"}}
    """
    flat_metadata_keys = [k for k in row if k.startswith("metadata.")]

    if not flat_metadata_keys:
        return  # Nothing to normalize

    # Build the nested dict from the flat keys.
    # Skip None values — they come from empty CSV cells after _normalize_empty_strings
    # runs, and Pydantic should use field defaults (e.g. source → Source.api) instead
    # of receiving an explicit None that would fail non-Optional field validation.
    nested: Dict[str, Any] = {}
    for key in flat_metadata_keys:
        sub_key = key.split(".", 1)[1]   # "metadata.source" → "source"
        value = row.pop(key)             # Remove flat key regardless
        if value is not None:
            nested[sub_key] = value      # Only include non-None values in nested dict

    # Merge with any existing metadata dict (prefer flat keys over nested).
    existing = row.get("metadata")
    if isinstance(existing, dict):
        existing.update(nested)
    else:
        row["metadata"] = nested


def _normalize_empty_strings(row: Dict[str, Any]) -> None:
    """
    Convert empty strings to None, in-place.

    CSV and XML files represent missing/optional values as empty strings ("").
    Pydantic Optional fields expect None, not "", so we normalise them here.
    Only top-level string values are checked; nested dicts are handled
    recursively so metadata sub-fields are also cleaned up.
    """
    for key, value in list(row.items()):
        if isinstance(value, str) and value.strip() == "":
            row[key] = None
        elif isinstance(value, dict):
            _normalize_empty_strings(value)


def _normalize_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """
    Apply all normalization steps to a raw parsed row.

    Order matters:
      1. Empty strings → None (must run before metadata extraction)
      2. Tags string → list
      3. Flat metadata keys → nested dict

    Returns the same dict (modified in-place) for convenience.
    """
    _normalize_empty_strings(row)
    _normalize_tags(row)
    _normalize_metadata(row)
    return row


# ── Batch processing ───────────────────────────────────────────────────────────


def _process_rows(rows: List[Dict[str, Any]]) -> ImportSummary:
    """
    Validate and create tickets for a list of raw row dicts.

    Processes every row — a failed row does not stop subsequent rows.
    Returns an ImportSummary with full details of successes and failures.
    """
    tickets: List[Ticket] = []
    errors:  List[ImportError] = []

    for row_number, raw_row in enumerate(rows, start=1):
        normalized = _normalize_row(dict(raw_row))  # Work on a copy
        ticket, error = _validate_and_create_row(normalized, row_number)

        if ticket is not None:
            tickets.append(ticket)
        else:
            errors.append(error)

    return ImportSummary(
        total=len(rows),
        successful=len(tickets),
        failed=len(errors),
        tickets=tickets,
        errors=errors,
    )


# ── CSV parser ─────────────────────────────────────────────────────────────────


def import_csv(content: bytes) -> ImportSummary:
    """
    Parse a CSV file and import all rows as tickets.

    CSV format requirements:
      - First row must be column headers matching Ticket field names.
      - Required headers: customer_id, customer_email, customer_name,
                          subject, description, category, priority
      - Optional headers: status, assigned_to, tags, metadata.source,
                          metadata.browser, metadata.device_type
      - Tags: use a quoted comma-separated cell  →  "billing,refund"
      - Metadata: use dot-notation headers       →  metadata.source

    Handles UTF-8 BOM (byte-order mark) automatically, so files exported
    from Excel work without any preprocessing.

    Raises ValueError if the file cannot be decoded or parsed as CSV.
    """
    try:
        # 'utf-8-sig' silently strips the BOM that Excel adds to CSV exports.
        text = content.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text))
        rows = [dict(row) for row in reader]
    except UnicodeDecodeError as exc:
        raise ValueError(f"CSV file encoding error — use UTF-8: {exc}") from exc
    except Exception as exc:
        raise ValueError(f"Cannot parse CSV file: {exc}") from exc

    if not rows:
        raise ValueError("CSV file is empty or contains only headers")

    return _process_rows(rows)


# ── JSON parser ────────────────────────────────────────────────────────────────


def import_json(content: bytes) -> ImportSummary:
    """
    Parse a JSON file and import all ticket objects.

    Accepts two JSON structures:
      1. Bare array:       [ { "customer_id": "...", ... }, ... ]
      2. Envelope object:  { "tickets": [ { ... }, ... ] }

    The envelope format is recommended — it's more extensible and allows
    metadata (like a schema version) to live alongside the ticket array.

    Raises ValueError with line/column info if the JSON is malformed.
    """
    try:
        data = json.loads(content.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Cannot parse JSON file — invalid JSON "
            f"(line {exc.lineno}, column {exc.colno}): {exc.msg}"
        ) from exc
    except UnicodeDecodeError as exc:
        raise ValueError(f"JSON file encoding error — use UTF-8: {exc}") from exc

    # Unwrap either format into a plain list.
    if isinstance(data, list):
        rows = data
    elif isinstance(data, dict) and "tickets" in data:
        rows = data["tickets"]
        if not isinstance(rows, list):
            raise ValueError(
                "JSON 'tickets' key must be an array, "
                f"got {type(rows).__name__} instead"
            )
    else:
        raise ValueError(
            "JSON must be either:\n"
            "  • A top-level array of ticket objects: [ {...}, ... ]\n"
            "  • An object with a 'tickets' array:    { \"tickets\": [ {...}, ... ] }"
        )

    if not rows:
        raise ValueError("JSON file contains no ticket records")

    return _process_rows(rows)


# ── XML parser ─────────────────────────────────────────────────────────────────


def _xml_element_to_dict(element: ET.Element) -> Dict[str, Any]:
    """
    Recursively convert an XML element and its children to a Python dict.

    Handles two array conventions for tags:
      • Comma string: <tags>billing,refund</tags>
        → {"tags": "billing,refund"}  (normalized later by _normalize_tags)
      • Repeated children: <tags><tag>billing</tag><tag>refund</tag></tags>
        → {"tags": ["billing", "refund"]}

    All other elements with children become nested dicts.
    """
    result: Dict[str, Any] = {}

    for child in element:
        if len(child) == 0:
            # Leaf element — grab its text content.
            result[child.tag] = child.text.strip() if child.text else ""
        else:
            # Element with children — check if they are repeated (array).
            child_tags = [grandchild.tag for grandchild in child]
            unique_tags = set(child_tags)

            if len(unique_tags) == 1 and len(child_tags) > 1:
                # Multiple children all share the same tag → treat as an array.
                # (e.g. <tags><tag>billing</tag><tag>refund</tag></tags>)
                # Single-child elements fall through to the dict branch below.
                tag_name = child_tags[0]
                result[child.tag] = [
                    (gc.text.strip() if gc.text else "")
                    for gc in child
                    if gc.tag == tag_name
                ]
            else:
                # Mixed children, or a single child element → recurse into a nested dict.
                result[child.tag] = _xml_element_to_dict(child)

    return result


def import_xml(content: bytes) -> ImportSummary:
    """
    Parse an XML file and import all ticket elements.

    Expected XML structure:

        <tickets>
          <ticket>
            <customer_id>cust-001</customer_id>
            <customer_email>alice@example.com</customer_email>
            ...
            <tags>
              <tag>billing</tag>
              <tag>refund</tag>
            </tags>
            <metadata>
              <source>web_form</source>
              <device_type>desktop</device_type>
            </metadata>
          </ticket>
        </tickets>

    Tags may alternatively be written as a comma string:
        <tags>billing,refund</tags>

    Raises ValueError if the XML is malformed or cannot be parsed.
    """
    try:
        root = ET.fromstring(content.decode("utf-8"))
    except ET.ParseError as exc:
        raise ValueError(f"Cannot parse XML file — malformed XML: {exc}") from exc
    except UnicodeDecodeError as exc:
        raise ValueError(f"XML file encoding error — use UTF-8: {exc}") from exc

    # Support both <tickets><ticket>…</ticket></tickets>
    # and a single top-level <ticket>…</ticket>.
    if root.tag == "ticket":
        ticket_elements = [root]
    else:
        ticket_elements = root.findall("ticket")

    if not ticket_elements:
        raise ValueError(
            "XML file contains no <ticket> elements. "
            "Expected structure: <tickets><ticket>…</ticket></tickets>"
        )

    rows = [_xml_element_to_dict(elem) for elem in ticket_elements]
    return _process_rows(rows)
