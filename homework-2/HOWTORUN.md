# HOWTORUN.md — Setup & Run Guide

> Step-by-step instructions for running the Customer Support Ticket API locally.
> Includes copy-paste cURL examples for every endpoint.
>
> Related: [README.md](README.md) · [docs/API_REFERENCE.md](docs/API_REFERENCE.md) · [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

---

## Prerequisites

- **Python 3.11+** — check with `python3 --version`
- **pip** — comes with Python; check with `pip3 --version`
- No database, no Docker, no external services needed

---

## 1. Install Dependencies

From the `homework-2/` directory:

```bash
pip install -r requirements.txt
```

This installs:
- `fastapi` — web framework
- `uvicorn[standard]` — ASGI server
- `pydantic[email]` — data validation + email format checking
- `python-multipart` — required for file uploads

---

## 2. Start the Server

```bash
uvicorn src.main:app --reload
```

You should see:

```
INFO:     Started server process [12345]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
```

> **`--reload`** watches for file changes and restarts automatically — great for development.
> Drop it in production.

**Custom port:**
```bash
uvicorn src.main:app --reload --port 8080
```

---

## 3. Verify It's Running

```bash
curl http://localhost:8000/health
```

Expected response:
```json
{"status": "ok", "ticket_count": 0, "version": "1.0.0"}
```

**Interactive API docs** (Swagger UI):
```
http://localhost:8000/docs
```

---

## 4. Create a Ticket

```bash
curl -s -X POST http://localhost:8000/tickets \
  -H "Content-Type: application/json" \
  -d '{
    "customer_id": "cust-001",
    "customer_email": "alice@example.com",
    "customer_name": "Alice Johnson",
    "subject": "Cannot log into my account",
    "description": "I have been unable to log in since yesterday. I get the error Invalid credentials even though I reset my password twice.",
    "category": "account_access",
    "priority": "urgent"
  }'
```

Expected response (`201 Created`):
```json
{
  "customer_id": "cust-001",
  "customer_email": "alice@example.com",
  "customer_name": "Alice Johnson",
  "subject": "Cannot log into my account",
  "description": "I have been unable to log in since yesterday...",
  "category": "account_access",
  "priority": "urgent",
  "assigned_to": null,
  "tags": [],
  "metadata": {"source": "api", "browser": null, "device_type": null},
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "new",
  "created_at": "2026-05-24T15:46:13.132462+00:00",
  "updated_at": "2026-05-24T15:46:13.132462+00:00",
  "resolved_at": null
}
```

**Save the `id`** — you'll need it for GET, PUT, DELETE.

---

## 5. Bulk Import Tickets

### From CSV
```bash
curl -s -X POST http://localhost:8000/tickets/import \
  -F "file=@demo/sample_tickets.csv" | python3 -m json.tool
```

### From JSON
```bash
curl -s -X POST http://localhost:8000/tickets/import \
  -F "file=@demo/sample_tickets.json" | python3 -m json.tool
```

### From XML
```bash
curl -s -X POST http://localhost:8000/tickets/import \
  -F "file=@demo/sample_tickets.xml" | python3 -m json.tool
```

Expected response (`201 Created` — all rows succeed):
```json
{
  "total": 15,
  "successful": 15,
  "failed": 0,
  "tickets": [...],
  "errors": []
}
```

If some rows fail (`207 Multi-Status`):
```json
{
  "total": 15,
  "successful": 13,
  "failed": 2,
  "tickets": [...],
  "errors": [
    {
      "row": 4,
      "raw_data": {"customer_email": "not-an-email", ...},
      "errors": ["customer_email: value is not a valid email address"]
    }
  ]
}
```

---

## 6. List Tickets

### All tickets (newest first)
```bash
curl -s http://localhost:8000/tickets | python3 -m json.tool
```

### Filter by status
```bash
curl -s "http://localhost:8000/tickets?status=new"
curl -s "http://localhost:8000/tickets?status=in_progress"
curl -s "http://localhost:8000/tickets?status=resolved"
```

### Filter by priority
```bash
curl -s "http://localhost:8000/tickets?priority=urgent"
curl -s "http://localhost:8000/tickets?priority=high"
```

### Filter by category
```bash
curl -s "http://localhost:8000/tickets?category=billing_question"
curl -s "http://localhost:8000/tickets?category=technical_issue"
```

### Multiple filters (AND logic)
```bash
# Urgent tickets that are still new — the support queue
curl -s "http://localhost:8000/tickets?priority=urgent&status=new"

# High-priority billing issues assigned to a specific agent
curl -s "http://localhost:8000/tickets?priority=high&category=billing_question&assigned_to=agent-sarah"
```

### Filter by tags (ALL must match)
```bash
# Tickets tagged with both "billing" AND "refund"
curl -s "http://localhost:8000/tickets?tags=billing,refund"
```

---

## 7. Get a Single Ticket

Replace `<ticket-id>` with the UUID from the create response:

```bash
curl -s http://localhost:8000/tickets/<ticket-id> | python3 -m json.tool
```

Not found response (`404`):
```json
{"detail": "Ticket '550e8400-...' not found"}
```

---

## 8. Update a Ticket

### Assign and change status
```bash
curl -s -X PUT http://localhost:8000/tickets/<ticket-id> \
  -H "Content-Type: application/json" \
  -d '{"status": "in_progress", "assigned_to": "agent-sarah"}'
```

### Resolve a ticket (auto-stamps `resolved_at`)
```bash
curl -s -X PUT http://localhost:8000/tickets/<ticket-id> \
  -H "Content-Type: application/json" \
  -d '{"status": "resolved"}'
```

The response will include `resolved_at` set to the current UTC time.

### Update tags and priority
```bash
curl -s -X PUT http://localhost:8000/tickets/<ticket-id> \
  -H "Content-Type: application/json" \
  -d '{"priority": "high", "tags": ["billing", "escalated"]}'
```

> Only fields you include are changed. Everything else stays the same.

---

## 9. Delete a Ticket

```bash
curl -s -o /dev/null -w "%{http_code}" \
  -X DELETE http://localhost:8000/tickets/<ticket-id>
```

Returns `204` (no body) on success, `404` if not found.

---

## 10. Auto-Classify a Ticket

### Run classification on an existing ticket

```bash
curl -s -X POST http://localhost:8000/tickets/<ticket-id>/auto-classify \
  | python3 -m json.tool
```

The response is the full ticket with updated `category`, `priority`, and a new `classification` field:

```json
{
  "id": "550e8400-...",
  "category": "billing_question",
  "priority": "medium",
  "classification": {
    "category": "billing_question",
    "category_confidence": 0.86,
    "priority": "medium",
    "priority_confidence": 1.0,
    "matched_keywords": ["billing", "charge", "invoice", "payment", "refund"],
    "classified_at": "2026-05-26T10:00:00+00:00"
  }
}
```

### Auto-classify at creation time

Pass `"auto_classify": true` in the request body — the ticket is classified immediately and the submitted `category`/`priority` are overwritten by the classifier:

```bash
curl -s -X POST http://localhost:8000/tickets \
  -H "Content-Type: application/json" \
  -d '{
    "customer_id":    "cust-002",
    "customer_email": "bob@example.com",
    "customer_name":  "Bob",
    "subject":        "Production server is completely down",
    "description":    "Our production environment has an outage. All users cannot access the app. Critical emergency, needs immediate fix.",
    "category":       "other",
    "priority":       "low",
    "auto_classify":  true
  }'
# Result: category="technical_issue", priority="urgent" — classifier overrides
```

### Auto-classify in bulk import

Add `"auto_classify": true` to individual rows in your JSON import file:

```json
{"tickets": [
  {
    "customer_id": "c1", "customer_email": "alice@example.com", "customer_name": "Alice",
    "subject": "Refund needed for double charge",
    "description": "I was charged twice. Please process a refund.",
    "category": "other", "priority": "low",
    "auto_classify": true
  }
]}
```

> ⚠️ The `auto_classify` flag is **not stored** on the ticket — it only controls whether classification runs at creation time.

---

## 11. Validation Error Examples

### Short description (too few characters)
```bash
curl -s -X POST http://localhost:8000/tickets \
  -H "Content-Type: application/json" \
  -d '{"customer_id":"c1","customer_email":"x@x.com","customer_name":"Test","subject":"Sub","description":"short","category":"other","priority":"low"}'
```

Response (`422 Unprocessable Entity`):
```json
{
  "detail": [
    {
      "type": "value_error",
      "loc": ["body", "description"],
      "msg": "Value error, description is too short (5 chars); min is 10"
    }
  ]
}
```

### Invalid enum value
```bash
curl -s "http://localhost:8000/tickets?priority=super_urgent"
```

Response (`422`):
```json
{
  "detail": [
    {
      "type": "enum",
      "loc": ["query", "priority"],
      "msg": "Input should be 'urgent', 'high', 'medium' or 'low'"
    }
  ]
}
```

### Unsupported file type
```bash
echo "test" > /tmp/test.txt
curl -s -X POST http://localhost:8000/tickets/import -F "file=@/tmp/test.txt"
```

Response (`415 Unsupported Media Type`):
```json
{"detail": "Unsupported file type. Please upload a .csv, .json, or .xml file."}
```

---

## Enum Reference

| Field | Allowed Values |
|-------|---------------|
| `category` | `account_access` · `technical_issue` · `billing_question` · `feature_request` · `bug_report` · `other` |
| `priority` | `urgent` · `high` · `medium` · `low` |
| `status` | `new` · `in_progress` · `waiting_customer` · `resolved` · `closed` |
| `metadata.source` | `web_form` · `email` · `api` · `chat` · `phone` |
| `metadata.device_type` | `desktop` · `mobile` · `tablet` |

---

## Stopping the Server

```
Ctrl+C
```

> ⚠️ **All tickets are lost on restart.** The store is in-memory — Phase 1 has no database.

---

*Full endpoint schemas → [docs/API_REFERENCE.md](docs/API_REFERENCE.md)*
*Architecture deep-dive → [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)*
