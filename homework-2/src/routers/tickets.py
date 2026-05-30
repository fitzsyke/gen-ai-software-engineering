"""
tickets.py — HTTP route handlers for the Ticket API.

This module is intentionally thin: it handles HTTP concerns (request parsing,
status codes, error responses) and delegates all business logic to the service
layer. No storage or validation logic lives here.

Endpoints:
  POST   /tickets                    Create a new ticket
  POST   /tickets/import             Bulk import from CSV / JSON / XML file
  GET    /tickets                    List tickets (filterable by status, category, etc.)
  GET    /tickets/{id}               Get a single ticket by UUID
  PUT    /tickets/{id}               Partial update of a ticket
  DELETE /tickets/{id}               Delete a ticket
  POST   /tickets/{id}/auto-classify Run keyword-based classification on a ticket

See docs/api/ for full request/response documentation and cURL examples.
"""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from fastapi.responses import JSONResponse

from ..models.ticket import (
    Category,
    FilterParams,
    ImportSummary,
    Priority,
    Status,
    Ticket,
    TicketCreate,
    TicketUpdate,
)
from ..services import import_service, ticket_service

# All routes in this router share the /tickets prefix and the "tickets" OpenAPI tag.
router = APIRouter(prefix="/tickets", tags=["tickets"])


# ── POST /tickets ──────────────────────────────────────────────────────────────


@router.post(
    "",
    status_code=201,
    response_model=Ticket,
    summary="Create a new support ticket",
    response_description="The newly created ticket",
)
async def create_ticket(data: TicketCreate) -> Ticket:
    """
    Create a new support ticket.

    All required fields must be provided. The server automatically sets:
    - `id`         — a new UUID
    - `status`     — starts as `new`
    - `created_at` / `updated_at` — current UTC time

    Returns the full ticket object with a **201 Created** status.
    """
    return ticket_service.create_ticket(data)


# ── POST /tickets/import ───────────────────────────────────────────────────────
# IMPORTANT: this route must be defined BEFORE /{ticket_id} so FastAPI doesn't
# try to match the literal string "import" as a UUID parameter.


@router.post(
    "/import",
    summary="Bulk import tickets from a file",
    response_description="Import summary with success/failure counts",
)
async def import_tickets(file: UploadFile = File(...)) -> JSONResponse:
    """
    Upload a CSV, JSON, or XML file to bulk-create tickets.

    **Supported formats:**
    - `.csv` — Headers must match field names; tags use quoted comma values;
               metadata columns use dot-notation (`metadata.source`).
    - `.json` — Bare array `[{...}]` or envelope `{"tickets": [{...}]}`.
    - `.xml`  — `<tickets><ticket>…</ticket></tickets>` structure.

    **Response status codes:**
    - `201 Created`        — All rows imported successfully.
    - `207 Multi-Status`   — Some rows succeeded, some failed (see `errors`).
    - `400 Bad Request`    — File is malformed and cannot be parsed at all.
    - `415 Unsupported`    — File extension is not `.csv`, `.json`, or `.xml`.

    The response body always contains the full `ImportSummary` with per-row
    error details for any failed rows.
    """
    content  = await file.read()
    filename = (file.filename or "").lower()

    # Route to the correct parser based on file extension.
    try:
        if filename.endswith(".csv"):
            summary = import_service.import_csv(content)
        elif filename.endswith(".json"):
            summary = import_service.import_json(content)
        elif filename.endswith(".xml"):
            summary = import_service.import_xml(content)
        else:
            raise HTTPException(
                status_code=415,
                detail=(
                    "Unsupported file type. "
                    "Please upload a .csv, .json, or .xml file."
                ),
            )
    except ValueError as exc:
        # The file is malformed (bad encoding, invalid XML structure, etc.)
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # 207 Multi-Status when at least one row succeeded and at least one failed.
    # This tells the client "partial success" rather than a binary pass/fail.
    if summary.failed > 0 and summary.successful > 0:
        status_code = 207
    elif summary.failed > 0 and summary.successful == 0:
        # All rows failed — still return 201 so the client gets the error details
        # in the ImportSummary body rather than an exception.
        status_code = 201
    else:
        status_code = 201

    return JSONResponse(
        status_code=status_code,
        content=summary.model_dump(mode="json"),
    )


# ── POST /tickets/{ticket_id}/auto-classify ────────────────────────────────────
# Defined before /{ticket_id} routes so FastAPI evaluates the more-specific
# two-segment path correctly, though FastAPI handles this fine either way.


@router.post(
    "/{ticket_id}/auto-classify",
    response_model=Ticket,
    status_code=200,
    summary="Auto-classify a ticket",
    response_description="The ticket with updated category, priority, and classification result",
)
async def auto_classify_ticket(ticket_id: UUID) -> Ticket:
    """
    Run keyword-based auto-classification on an existing ticket.

    Analyses the ticket's **subject** and **description** for known keywords
    to assign the most likely `category` and `priority`. Both fields are
    overwritten on the ticket with the classifier's output.

    The full `ClassificationResult` (including matched keywords and confidence
    scores) is stored on the ticket's `classification` field and returned in
    the response.

    **Can be called multiple times** — each call re-classifies from scratch,
    replacing any previous classification result.

    Returns **404 Not Found** if no ticket exists with that id.
    """
    ticket = ticket_service.auto_classify_ticket(str(ticket_id))
    if ticket is None:
        raise HTTPException(
            status_code=404,
            detail=f"Ticket '{ticket_id}' not found",
        )
    return ticket


# ── GET /tickets ───────────────────────────────────────────────────────────────


@router.get(
    "",
    response_model=List[Ticket],
    summary="List all tickets",
    response_description="List of tickets matching the filters, newest first",
)
async def list_tickets(
    status:      Optional[Status]   = Query(None, description="Filter by ticket status"),
    category:    Optional[Category] = Query(None, description="Filter by category"),
    priority:    Optional[Priority] = Query(None, description="Filter by priority level"),
    assigned_to: Optional[str]      = Query(None, description="Filter by assigned agent name/id"),
    tags:        Optional[str]      = Query(
        None,
        description="Comma-separated tags; ticket must have ALL listed tags. Example: billing,refund",
    ),
) -> List[Ticket]:
    """
    Return all tickets, optionally filtered.

    All filters are optional and combine with **AND** logic — a ticket must
    satisfy every filter you supply to appear in the results.

    Results are sorted **newest first** (most recently created).

    **Filter examples:**
    - `?status=new` — only open/unassigned tickets
    - `?priority=urgent&status=new` — urgent tickets not yet picked up
    - `?tags=billing,refund` — tickets tagged with both 'billing' and 'refund'
    """
    filters = FilterParams(
        status=status,
        category=category,
        priority=priority,
        assigned_to=assigned_to,
        tags=tags,
    )
    return ticket_service.list_tickets(filters)


# ── GET /tickets/{ticket_id} ───────────────────────────────────────────────────


@router.get(
    "/{ticket_id}",
    response_model=Ticket,
    summary="Get a ticket by ID",
    response_description="The requested ticket",
)
async def get_ticket(ticket_id: UUID) -> Ticket:
    """
    Retrieve a single ticket by its UUID.

    Returns **404 Not Found** if no ticket exists with that id.
    """
    ticket = ticket_service.get_ticket(str(ticket_id))
    if ticket is None:
        raise HTTPException(
            status_code=404,
            detail=f"Ticket '{ticket_id}' not found",
        )
    return ticket


# ── PUT /tickets/{ticket_id} ───────────────────────────────────────────────────


@router.put(
    "/{ticket_id}",
    response_model=Ticket,
    summary="Update a ticket",
    response_description="The updated ticket",
)
async def update_ticket(ticket_id: UUID, data: TicketUpdate) -> Ticket:
    """
    Update an existing ticket (partial update).

    Only the fields you include in the request body are changed.
    Omitted fields keep their current values.

    **Special behaviour:**
    - Setting `status` to `resolved` automatically stamps `resolved_at`
      with the current UTC time (only if not already resolved).

    Returns **404 Not Found** if no ticket exists with that id.
    """
    ticket = ticket_service.update_ticket(str(ticket_id), data)
    if ticket is None:
        raise HTTPException(
            status_code=404,
            detail=f"Ticket '{ticket_id}' not found",
        )
    return ticket


# ── DELETE /tickets/{ticket_id} ───────────────────────────────────────────────


@router.delete(
    "/{ticket_id}",
    status_code=204,
    summary="Delete a ticket",
    response_description="No content — ticket was deleted",
)
async def delete_ticket(ticket_id: UUID) -> None:
    """
    Permanently delete a ticket.

    Returns **204 No Content** on success (no response body).
    Returns **404 Not Found** if no ticket exists with that id.
    """
    deleted = ticket_service.delete_ticket(str(ticket_id))
    if not deleted:
        raise HTTPException(
            status_code=404,
            detail=f"Ticket '{ticket_id}' not found",
        )
