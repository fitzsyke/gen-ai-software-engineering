"""
ticket_service.py — Business logic for ticket CRUD operations.

This layer sits between the HTTP router and the storage layer.
It has no knowledge of HTTP (no Request, Response, or status codes here) —
that belongs in the router. It also has no knowledge of how data is stored —
that belongs in the store.

Functions:
  create_ticket(data)              → Ticket
  get_ticket(id)                   → Ticket | None
  list_tickets(filters)            → List[Ticket]
  update_ticket(id, data)          → Ticket | None
  delete_ticket(id)                → bool
  auto_classify_ticket(id)         → Ticket | None
"""

from datetime import datetime, timezone
from typing import List, Optional
from uuid import uuid4

from ..models.ticket import (
    FilterParams,
    Status,
    Ticket,
    TicketCreate,
    TicketUpdate,
)
from ..storage.ticket_store import store


def create_ticket(data: TicketCreate) -> Ticket:
    """
    Create a new ticket from validated input data.

    The service layer adds the server-managed fields — id, timestamps, and
    an initial status of 'new' — before handing the ticket to the store.

    If data.auto_classify is True, the ticket is classified immediately after
    creation: its category and priority are overwritten with the classifier's
    output and a ClassificationResult is stored on the ticket.

    Note: auto_classify is a request-time flag and is NOT stored on the ticket.
    """
    from . import classify_service  # deferred to avoid circular-import risk

    now = datetime.now(timezone.utc)

    # auto_classify is a request flag — exclude it from the stored ticket.
    ticket_fields = data.model_dump(exclude={"auto_classify"})

    ticket = Ticket(
        id=uuid4(),
        status=Status.new,
        created_at=now,
        updated_at=now,
        resolved_at=None,
        **ticket_fields,
    )

    saved = store.add(ticket)

    # Run auto-classification after the ticket is saved so it has a valid id.
    if data.auto_classify:
        result = classify_service.classify(saved.subject, saved.description)
        classified = saved.model_copy(update={
            "category":       result.category,
            "priority":       result.priority,
            "classification": result,
            "updated_at":     now,
        })
        saved = store.update(str(saved.id), classified)

    return saved


def get_ticket(ticket_id: str) -> Optional[Ticket]:
    """
    Look up a ticket by its UUID string.

    Returns the Ticket if found, or None if no ticket has that id.
    """
    return store.get(ticket_id)


def list_tickets(filters: FilterParams) -> List[Ticket]:
    """
    Return all tickets, optionally filtered.

    Filters combine with AND logic — a ticket must match every supplied
    filter to appear in the results. Omitted filters are ignored.

    Tag filtering uses ALL-match semantics:
      ?tags=billing,refund  →  tickets that have BOTH 'billing' AND 'refund'

    Results are sorted newest-first (most recently created at the top).
    """
    tickets = store.all()

    # Apply each filter only if a value was provided.
    if filters.status:
        tickets = [t for t in tickets if t.status == filters.status]

    if filters.category:
        tickets = [t for t in tickets if t.category == filters.category]

    if filters.priority:
        tickets = [t for t in tickets if t.priority == filters.priority]

    if filters.assigned_to:
        tickets = [t for t in tickets if t.assigned_to == filters.assigned_to]

    if filters.tags:
        # Split "billing,refund" into {"billing", "refund"} and require all.
        required_tags = {tag.strip() for tag in filters.tags.split(",") if tag.strip()}
        tickets = [t for t in tickets if required_tags.issubset(set(t.tags))]

    # Newest first — most relevant for support queues.
    tickets.sort(key=lambda t: t.created_at, reverse=True)
    return tickets


def update_ticket(ticket_id: str, data: TicketUpdate) -> Optional[Ticket]:
    """
    Apply a partial update to an existing ticket.

    Only the fields present in the TicketUpdate payload are changed;
    everything else is preserved from the existing ticket.

    Special behaviour:
      - resolved_at is automatically stamped (UTC) when status is set to
        'resolved' for the first time. Re-resolving a ticket keeps the
        original resolved_at timestamp.

    Returns the updated Ticket, or None if the ticket does not exist.
    """
    existing = store.get(ticket_id)
    if existing is None:
        return None

    now = datetime.now(timezone.utc)

    # Build the dict of fields to change, skipping fields not provided.
    changes = data.model_dump(exclude_none=True)

    # Auto-stamp resolved_at when transitioning to 'resolved'.
    resolved_at = existing.resolved_at
    if changes.get("status") == Status.resolved and resolved_at is None:
        resolved_at = now

    # Always bump updated_at.
    changes["updated_at"] = now
    changes["resolved_at"] = resolved_at

    updated_ticket = existing.model_copy(update=changes)
    return store.update(ticket_id, updated_ticket)


def delete_ticket(ticket_id: str) -> bool:
    """
    Permanently remove a ticket from the store.

    Returns True if the ticket existed and was deleted, False if not found.
    """
    return store.delete(ticket_id)


def auto_classify_ticket(ticket_id: str) -> Optional[Ticket]:
    """
    Run auto-classification on an existing ticket and update it in place.

    Overwrites the ticket's category and priority with the classifier's output.
    Stores the full ClassificationResult on the ticket's 'classification' field.

    Can be called multiple times — each call re-classifies from scratch and
    replaces any previous ClassificationResult.

    Returns the updated Ticket, or None if no ticket exists with that id.
    """
    from . import classify_service  # deferred to avoid circular-import risk

    existing = store.get(ticket_id)
    if existing is None:
        return None

    result = classify_service.classify(existing.subject, existing.description)

    updated = existing.model_copy(update={
        "category":       result.category,
        "priority":       result.priority,
        "classification": result,
        "updated_at":     datetime.now(timezone.utc),
    })

    return store.update(ticket_id, updated)
