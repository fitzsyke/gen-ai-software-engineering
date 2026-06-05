"""
test_ticket_model.py — Unit tests for Pydantic model validation.

Tests field validators, enum constraints, default values, and the
TicketCreate / TicketUpdate / FilterParams models in isolation —
no HTTP layer, no storage.

Coverage targets:
  src/models/ticket.py — all validators and model behaviours
"""

import pytest
from pydantic import ValidationError

from src.models.ticket import (
    Category,
    ClassificationResult,
    DeviceType,
    FilterParams,
    Priority,
    Source,
    Status,
    Ticket,
    TicketCreate,
    TicketMetadata,
    TicketUpdate,
)


# ── TicketCreate — required fields ─────────────────────────────────────────────


def test_ticket_create_valid():
    t = TicketCreate(
        customer_id="c1",
        customer_email="alice@example.com",
        customer_name="Alice",
        subject="Cannot log in",
        description="I cannot access my account since yesterday evening.",
        category=Category.account_access,
        priority=Priority.urgent,
    )
    assert t.customer_id == "c1"
    assert t.category == Category.account_access
    assert t.auto_classify is False  # default


def test_ticket_create_missing_required_field():
    with pytest.raises(ValidationError) as exc_info:
        TicketCreate(
            customer_email="alice@example.com",
            customer_name="Alice",
            subject="Test",
            description="Long enough description here please.",
            category=Category.other,
            priority=Priority.low,
        )
    assert "customer_id" in str(exc_info.value)


# ── Subject validator ──────────────────────────────────────────────────────────


def test_subject_too_long():
    with pytest.raises(ValidationError) as exc_info:
        TicketCreate(
            customer_id="c1",
            customer_email="a@b.com",
            customer_name="Alice",
            subject="x" * 201,
            description="A long enough description to pass validation here.",
            category=Category.other,
            priority=Priority.low,
        )
    assert "subject" in str(exc_info.value)


def test_subject_blank_whitespace():
    with pytest.raises(ValidationError):
        TicketCreate(
            customer_id="c1",
            customer_email="a@b.com",
            customer_name="Alice",
            subject="   ",
            description="A long enough description to pass validation here.",
            category=Category.other,
            priority=Priority.low,
        )


def test_subject_strips_leading_trailing_whitespace():
    t = TicketCreate(
        customer_id="c1",
        customer_email="a@b.com",
        customer_name="Alice",
        subject="  Hello world  ",
        description="A long enough description to pass validation here.",
        category=Category.other,
        priority=Priority.low,
    )
    assert t.subject == "Hello world"


# ── Description validator ──────────────────────────────────────────────────────


def test_description_too_short():
    with pytest.raises(ValidationError) as exc_info:
        TicketCreate(
            customer_id="c1",
            customer_email="a@b.com",
            customer_name="Alice",
            subject="Subject",
            description="short",
            category=Category.other,
            priority=Priority.low,
        )
    assert "description" in str(exc_info.value)


def test_description_too_long():
    with pytest.raises(ValidationError):
        TicketCreate(
            customer_id="c1",
            customer_email="a@b.com",
            customer_name="Alice",
            subject="Subject",
            description="x" * 2001,
            category=Category.other,
            priority=Priority.low,
        )


def test_description_exactly_10_chars():
    t = TicketCreate(
        customer_id="c1",
        customer_email="a@b.com",
        customer_name="Alice",
        subject="Subject",
        description="1234567890",
        category=Category.other,
        priority=Priority.low,
    )
    assert len(t.description) == 10


# ── Email validator ───────────────────────────────────────────────────────────


def test_invalid_email():
    with pytest.raises(ValidationError):
        TicketCreate(
            customer_id="c1",
            customer_email="not-an-email",
            customer_name="Alice",
            subject="Subject",
            description="A long enough description here.",
            category=Category.other,
            priority=Priority.low,
        )


def test_valid_email_accepted():
    t = TicketCreate(
        customer_id="c1",
        customer_email="alice+tag@example.co.uk",
        customer_name="Alice",
        subject="Subject",
        description="A long enough description here.",
        category=Category.other,
        priority=Priority.low,
    )
    assert "alice" in str(t.customer_email)


# ── Blank field validators ────────────────────────────────────────────────────


def test_customer_id_blank():
    with pytest.raises(ValidationError):
        TicketCreate(
            customer_id="   ",
            customer_email="a@b.com",
            customer_name="Alice",
            subject="Subject",
            description="A long enough description here.",
            category=Category.other,
            priority=Priority.low,
        )


def test_customer_name_blank():
    with pytest.raises(ValidationError):
        TicketCreate(
            customer_id="c1",
            customer_email="a@b.com",
            customer_name="",
            subject="Subject",
            description="A long enough description here.",
            category=Category.other,
            priority=Priority.low,
        )


# ── Tags validator ────────────────────────────────────────────────────────────


def test_tags_strips_whitespace_and_empties():
    t = TicketCreate(
        customer_id="c1",
        customer_email="a@b.com",
        customer_name="Alice",
        subject="Subject",
        description="A long enough description here.",
        category=Category.other,
        priority=Priority.low,
        tags=["  billing  ", "", "  refund"],
    )
    assert t.tags == ["billing", "refund"]


def test_tags_defaults_to_empty_list():
    t = TicketCreate(
        customer_id="c1",
        customer_email="a@b.com",
        customer_name="Alice",
        subject="Subject",
        description="A long enough description here.",
        category=Category.other,
        priority=Priority.low,
    )
    assert t.tags == []


# ── TicketUpdate ──────────────────────────────────────────────────────────────


def test_ticket_update_all_optional():
    update = TicketUpdate()
    assert update.status is None
    assert update.priority is None
    assert update.category is None


def test_ticket_update_partial():
    update = TicketUpdate(status=Status.in_progress, assigned_to="agent-1")
    assert update.status == Status.in_progress
    assert update.assigned_to == "agent-1"
    assert update.priority is None


def test_ticket_update_validates_subject_length():
    with pytest.raises(ValidationError):
        TicketUpdate(subject="x" * 201)


# ── TicketMetadata defaults ───────────────────────────────────────────────────


def test_metadata_defaults():
    meta = TicketMetadata()
    assert meta.source == Source.api
    assert meta.browser is None
    assert meta.device_type is None


def test_metadata_with_values():
    meta = TicketMetadata(source=Source.web_form, device_type=DeviceType.mobile)
    assert meta.source == Source.web_form
    assert meta.device_type == DeviceType.mobile


# ── FilterParams ──────────────────────────────────────────────────────────────


def test_filter_params_all_optional():
    fp = FilterParams()
    assert fp.status is None
    assert fp.category is None
    assert fp.priority is None
    assert fp.assigned_to is None
    assert fp.tags is None


# ── Enums ─────────────────────────────────────────────────────────────────────


def test_enums_serialize_as_strings():
    t = TicketCreate(
        customer_id="c1",
        customer_email="a@b.com",
        customer_name="Alice",
        subject="Subject",
        description="A long enough description here.",
        category=Category.billing_question,
        priority=Priority.medium,
    )
    dumped = t.model_dump()
    assert dumped["category"] == "billing_question"
    assert dumped["priority"] == "medium"
