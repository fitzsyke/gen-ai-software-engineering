"""
ticket.py — Core data models for the Customer Support Ticket system.

This module defines every Pydantic model used across the application:
  - Enum types        : Category, Priority, Status, Source, DeviceType
  - Sub-models        : TicketMetadata, ClassificationResult
  - Request bodies    : TicketCreate (POST), TicketUpdate (PUT)
  - Full model        : Ticket (stored object returned in responses)
  - Import types      : ImportError, ImportSummary (bulk-import responses)
  - Filter params     : FilterParams (used by GET /tickets query parameters)

All enums inherit from (str, Enum) so JSON serialization produces plain
strings ("urgent") instead of enum repr ("Priority.urgent").
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


# ── Enumerations ───────────────────────────────────────────────────────────────


class Category(str, Enum):
    """The type of issue the customer is reporting."""
    account_access  = "account_access"    # Login, password reset, 2FA problems
    technical_issue = "technical_issue"   # Bugs, errors, crashes, slow performance
    billing_question = "billing_question" # Payments, invoices, subscription, refunds
    feature_request  = "feature_request"  # Enhancement ideas, new functionality asks
    bug_report       = "bug_report"       # Confirmed defects with reproduction steps
    other            = "other"            # Anything that doesn't fit the categories above


class Priority(str, Enum):
    """How quickly the ticket should be addressed."""
    urgent = "urgent"   # Production down, security incident, can't access account
    high   = "high"     # Important blocker, ASAP resolution needed
    medium = "medium"   # Normal priority — the default for new tickets
    low    = "low"      # Minor issue, cosmetic bug, or a suggestion


class Status(str, Enum):
    """Lifecycle stage of the ticket."""
    new              = "new"              # Just created, not yet picked up
    in_progress      = "in_progress"      # Agent is actively working on it
    waiting_customer = "waiting_customer" # Waiting on more info from the customer
    resolved         = "resolved"         # Fix applied; resolved_at is stamped
    closed           = "closed"           # Ticket archived / no further action


class Source(str, Enum):
    """Channel through which the ticket was submitted."""
    web_form = "web_form"  # Customer filled in the support form on the website
    email    = "email"     # Ticket created from an inbound support email
    api      = "api"       # Created programmatically via this REST API
    chat     = "chat"      # Live chat session escalated to a ticket
    phone    = "phone"     # Phone call logged as a ticket


class DeviceType(str, Enum):
    """Type of device the customer was using when they reported the issue."""
    desktop = "desktop"
    mobile  = "mobile"
    tablet  = "tablet"


# ── Sub-models ─────────────────────────────────────────────────────────────────


class TicketMetadata(BaseModel):
    """
    Optional contextual info captured at ticket-creation time.
    Helps support agents reproduce issues (e.g. 'Chrome on mobile').
    """
    source:      Source              = Source.api   # How the ticket was submitted
    browser:     Optional[str]       = None         # Browser name/version, if known
    device_type: Optional[DeviceType] = None        # Device category, if known


# ── Classification result ──────────────────────────────────────────────────────


class ClassificationResult(BaseModel):
    """
    Result of an auto-classification run on a ticket.

    Stored on the ticket after POST /tickets/:id/auto-classify is called
    (or when a ticket is created with auto_classify=True).

    Fields:
      category             — classified category (may differ from submitted category)
      category_confidence  — 0.0–1.0; how confident the classifier is in category
      priority             — classified priority (may differ from submitted priority)
      priority_confidence  — 0.0–1.0; how confident the classifier is in priority
      matched_keywords     — every keyword found in the ticket text (subject + description)
      classified_at        — UTC timestamp of when classification ran
    """
    category:             Category
    category_confidence:  float = Field(ge=0.0, le=1.0)
    priority:             Priority
    priority_confidence:  float = Field(ge=0.0, le=1.0)
    matched_keywords:     List[str]
    classified_at:        datetime


# ── Request models ─────────────────────────────────────────────────────────────


class TicketCreate(BaseModel):
    """
    Payload for creating a new ticket (POST /tickets body).

    Required fields: customer_id, customer_email, customer_name,
                     subject, description, category, priority.
    Optional fields: assigned_to, tags, metadata.
    """
    customer_id:    str
    customer_email: EmailStr              # Validated against RFC-5322 email format
    customer_name:  str
    subject:        str                   # 1–200 characters
    description:    str                   # 10–2000 characters
    category:       Category
    priority:       Priority = Priority.medium
    assigned_to:    Optional[str]         = None
    tags:           List[str]             = []
    metadata:       TicketMetadata        = TicketMetadata()
    auto_classify:  bool                  = False  # If True, run auto-classification after creation

    # ── Field validators ───────────────────────────────────────────────────────

    @field_validator("subject")
    @classmethod
    def validate_subject(cls, value: str) -> str:
        """Subject must be between 1 and 200 characters (non-blank)."""
        value = value.strip()
        if not value:
            raise ValueError("subject must not be blank")
        if len(value) > 200:
            raise ValueError(f"subject is too long ({len(value)} chars); max is 200")
        return value

    @field_validator("description")
    @classmethod
    def validate_description(cls, value: str) -> str:
        """Description must be between 10 and 2000 characters."""
        value = value.strip()
        if len(value) < 10:
            raise ValueError(
                f"description is too short ({len(value)} chars); min is 10"
            )
        if len(value) > 2000:
            raise ValueError(
                f"description is too long ({len(value)} chars); max is 2000"
            )
        return value

    @field_validator("customer_id", "customer_name")
    @classmethod
    def validate_not_blank(cls, value: str) -> str:
        """customer_id and customer_name must not be blank or whitespace-only."""
        if not value.strip():
            raise ValueError("field must not be blank")
        return value.strip()

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, value: List[str]) -> List[str]:
        """Strip whitespace from each tag and drop empty strings."""
        return [t.strip() for t in value if t.strip()]


class TicketUpdate(BaseModel):
    """
    Payload for updating an existing ticket (PUT /tickets/:id body).

    Every field is Optional — only the fields you provide will be changed
    (partial / PATCH-style update semantics, even though the HTTP method is PUT).

    Setting status to 'resolved' automatically stamps resolved_at on the ticket.
    """
    customer_email: Optional[EmailStr]      = None
    customer_name:  Optional[str]           = None
    subject:        Optional[str]           = None  # 1–200 chars if provided
    description:    Optional[str]           = None  # 10–2000 chars if provided
    category:       Optional[Category]      = None
    priority:       Optional[Priority]      = None
    status:         Optional[Status]        = None
    assigned_to:    Optional[str]           = None
    tags:           Optional[List[str]]     = None
    metadata:       Optional[TicketMetadata] = None

    # Re-apply the same length rules as TicketCreate when values are provided.

    @field_validator("subject")
    @classmethod
    def validate_subject(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("subject must not be blank")
        if len(value) > 200:
            raise ValueError(f"subject is too long ({len(value)} chars); max is 200")
        return value

    @field_validator("description")
    @classmethod
    def validate_description(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        value = value.strip()
        if len(value) < 10:
            raise ValueError(
                f"description is too short ({len(value)} chars); min is 10"
            )
        if len(value) > 2000:
            raise ValueError(
                f"description is too long ({len(value)} chars); max is 2000"
            )
        return value

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, value: Optional[List[str]]) -> Optional[List[str]]:
        if value is None:
            return value
        return [t.strip() for t in value if t.strip()]


# ── Full stored model ──────────────────────────────────────────────────────────


class Ticket(TicketCreate):
    """
    The complete ticket object — what gets stored and returned by the API.

    Extends TicketCreate with server-managed fields:
      id          — generated UUID (never set by the client)
      status      — starts as 'new', updated via PUT
      created_at  — set at creation time
      updated_at  — updated on every PUT
      resolved_at — automatically stamped when status becomes 'resolved'
    """
    id:             UUID
    status:         Status                          = Status.new
    created_at:     datetime
    updated_at:     datetime
    resolved_at:    Optional[datetime]              = None
    classification: Optional[ClassificationResult] = None  # Set after auto-classify runs

    model_config = ConfigDict(
        # Serialize UUID and datetime to strings in JSON responses.
        json_encoders={
            UUID:     str,
            datetime: lambda v: v.isoformat(),
        }
    )


# ── Bulk import response models ────────────────────────────────────────────────


class ImportError(BaseModel):
    """
    Describes a single row that failed validation during a bulk import.

    Fields:
      row      — 1-based row number in the source file (for easy debugging)
      raw_data — the raw dict parsed from the file before validation
      errors   — list of human-readable validation error messages
    """
    row:      int
    raw_data: Dict[str, Any]
    errors:   List[str]


class ImportSummary(BaseModel):
    """
    Response body for POST /tickets/import.

    Shows how many records were processed, how many succeeded, how many failed,
    the successfully created Ticket objects, and per-row error details.
    """
    total:      int                # Total rows in the uploaded file
    successful: int                # Rows that passed validation and were saved
    failed:     int                # Rows that failed validation (see errors list)
    tickets:    List[Ticket]       # The newly created Ticket objects
    errors:     List[ImportError]  # Per-row error details for failed rows


# ── Query filter params ────────────────────────────────────────────────────────


class FilterParams(BaseModel):
    """
    Query parameter container for GET /tickets.

    All fields are optional — omit any to skip that filter.
    Multiple filters combine with AND logic.

    The 'tags' field accepts a comma-separated string:
      ?tags=billing,urgent  →  only tickets that have BOTH tags
    """
    status:      Optional[Status]   = None
    category:    Optional[Category] = None
    priority:    Optional[Priority] = None
    assigned_to: Optional[str]      = None
    tags:        Optional[str]      = None  # e.g. "billing,refund"
