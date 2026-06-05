# Endpoints

> Related: [README.md](README.md) · [models.md](models.md) · [errors.md](errors.md)

---

## POST /tickets

Create a single new support ticket.

**Request body:** [TicketCreate](models.md#ticketcreate) (JSON)

| Response | When |
|----------|------|
| `201 Created` | Ticket created — returns full [Ticket](models.md#ticket) object |
| `422 Unprocessable Entity` | Validation failure (bad email, short description, invalid enum) |

```bash
curl -s -X POST http://localhost:8000/tickets \
  -H "Content-Type: application/json" \
  -d '{
    "customer_id":    "cust-001",
    "customer_email": "alice@example.com",
    "customer_name":  "Alice Johnson",
    "subject":        "Cannot log into my account",
    "description":    "Unable to access my account since yesterday evening.",
    "category":       "account_access",
    "priority":       "urgent",
    "tags":           ["account", "security"],
    "metadata":       {"source": "web_form", "device_type": "desktop"}
  }'
```

---

## POST /tickets/import

Bulk create tickets from an uploaded file. Processes every row — a failed row does not stop the rest.

**Request:** `multipart/form-data` with a single `file` field.  
**Supported extensions:** `.csv` · `.json` · `.xml`

| Response | When |
|----------|------|
| `201 Created` | All rows succeeded (or all failed — body has details) |
| `207 Multi-Status` | Some rows succeeded, some failed |
| `400 Bad Request` | File is malformed and cannot be parsed |
| `415 Unsupported Media Type` | Extension is not `.csv`, `.json`, or `.xml` |

**Returns:** [ImportSummary](models.md#importsummary)

### CSV format

Headers must match Ticket field names exactly.

```
customer_id,customer_email,customer_name,subject,description,category,priority,assigned_to,tags,metadata.source,metadata.device_type
cust-001,alice@example.com,Alice Johnson,Login issue,Cannot log in since yesterday.,account_access,urgent,,"account,security",web_form,desktop
```

- **Tags:** use a quoted comma-separated cell — `"account,security"`
- **Metadata:** use dot-notation headers — `metadata.source`, `metadata.device_type`
- **Encoding:** UTF-8 with or without BOM (Excel exports work automatically)
- **Empty cells:** treated as `null` for optional fields; tags empty cell → `[]`

```bash
curl -s -X POST http://localhost:8000/tickets/import -F "file=@demo/sample_tickets.csv"
```

### JSON format

Two accepted structures — bare array or envelope object:

```json
[{"customer_id": "cust-001", "customer_email": "alice@example.com", "...": "..."}]
```
```json
{"tickets": [{"customer_id": "cust-001", "...": "..."}]}
```

```bash
curl -s -X POST http://localhost:8000/tickets/import -F "file=@demo/sample_tickets.json"
```

### XML format

```xml
<tickets>
  <ticket>
    <customer_id>cust-001</customer_id>
    <customer_email>alice@example.com</customer_email>
    <customer_name>Alice Johnson</customer_name>
    <subject>Cannot log into my account</subject>
    <description>Unable to access my account since yesterday.</description>
    <category>account_access</category>
    <priority>urgent</priority>
    <tags><tag>account</tag><tag>security</tag></tags>
    <metadata>
      <source>web_form</source>
      <device_type>desktop</device_type>
    </metadata>
  </ticket>
</tickets>
```

Tags may also be written as a comma string: `<tags>account,security</tags>`

```bash
curl -s -X POST http://localhost:8000/tickets/import -F "file=@demo/sample_tickets.xml"
```

---

## GET /tickets

List all tickets. Results are sorted **newest first**.

**Query parameters** (all optional, combine with AND logic):

| Parameter | Type | Description | Example |
|-----------|------|-------------|---------|
| `status` | enum | Filter by ticket status | `?status=new` |
| `category` | enum | Filter by category | `?category=billing_question` |
| `priority` | enum | Filter by priority | `?priority=urgent` |
| `assigned_to` | string | Filter by assigned agent | `?assigned_to=agent-sarah` |
| `tags` | string | Comma-separated; ALL tags must be present | `?tags=billing,refund` |

| Response | When |
|----------|------|
| `200 OK` | Always — returns `[]` if nothing matches |
| `422` | Invalid enum value supplied as a filter |

```bash
# All tickets
curl -s http://localhost:8000/tickets

# Urgent tickets not yet assigned — the support queue
curl -s "http://localhost:8000/tickets?priority=urgent&status=new"

# Billing issues assigned to a specific agent
curl -s "http://localhost:8000/tickets?category=billing_question&assigned_to=agent-sarah"

# Tickets tagged with both "billing" AND "refund"
curl -s "http://localhost:8000/tickets?tags=billing,refund"
```

---

## GET /tickets/{id}

Retrieve a single ticket by its UUID.

| Response | When |
|----------|------|
| `200 OK` | Ticket found — returns full [Ticket](models.md#ticket) |
| `404 Not Found` | No ticket with that ID |
| `422` | `id` is not a valid UUID |

```bash
curl -s http://localhost:8000/tickets/550e8400-e29b-41d4-a716-446655440000
```

---

## PUT /tickets/{id}

Partially update an existing ticket. Only fields you include are changed — everything else is preserved.

**Request body:** [TicketUpdate](models.md#ticketupdate) (JSON)

> **Auto-stamp:** setting `status` to `resolved` automatically sets `resolved_at` to the current UTC time. The timestamp is preserved on all subsequent updates.

| Response | When |
|----------|------|
| `200 OK` | Updated — returns full updated [Ticket](models.md#ticket) |
| `404 Not Found` | No ticket with that ID |
| `422` | Validation failure on the updated fields |

```bash
# Pick up a ticket
curl -s -X PUT http://localhost:8000/tickets/550e8400-... \
  -H "Content-Type: application/json" \
  -d '{"status": "in_progress", "assigned_to": "agent-sarah"}'

# Resolve it (resolved_at is stamped automatically)
curl -s -X PUT http://localhost:8000/tickets/550e8400-... \
  -H "Content-Type: application/json" \
  -d '{"status": "resolved"}'

# Escalate priority and add a tag
curl -s -X PUT http://localhost:8000/tickets/550e8400-... \
  -H "Content-Type: application/json" \
  -d '{"priority": "urgent", "tags": ["escalated", "security"]}'
```

---

## DELETE /tickets/{id}

Permanently remove a ticket. There is no soft-delete or recovery.

| Response | When |
|----------|------|
| `204 No Content` | Deleted (no response body) |
| `404 Not Found` | No ticket with that ID |

```bash
# Returns 204 on success
curl -s -o /dev/null -w "%{http_code}" \
  -X DELETE http://localhost:8000/tickets/550e8400-e29b-41d4-a716-446655440000
```

---

## GET /health

Server health check. Use this to confirm the server is running and the store is wired.

| Response | When |
|----------|------|
| `200 OK` | Always |

```bash
curl -s http://localhost:8000/health
# {"status": "ok", "ticket_count": 42, "version": "1.0.0"}
```

---

## POST /tickets/{id}/auto-classify

Run keyword-based auto-classification on an existing ticket.

Analyses the ticket's **subject** and **description** for known keywords, then
assigns the most likely `category` and `priority`. Both fields are overwritten
on the stored ticket. The full `ClassificationResult` is stored on the ticket's
`classification` field and returned in the response.

Can be called multiple times — each call re-classifies from scratch.

| Response | When |
|----------|------|
| `200 OK` | Classification ran — returns updated [Ticket](models.md#ticket) with `classification` field set |
| `404 Not Found` | No ticket with that UUID |

```bash
# Run auto-classification on ticket <id>
curl -s -X POST http://localhost:8000/tickets/<id>/auto-classify | python3 -m json.tool
```

**Example response snippet:**
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

**Auto-classify at creation time:** Pass `"auto_classify": true` in `POST /tickets` or in bulk import rows:
```bash
curl -s -X POST http://localhost:8000/tickets \
  -H "Content-Type: application/json" \
  -d '{
    "customer_id": "c1",
    "customer_email": "alice@example.com",
    "customer_name": "Alice",
    "subject": "Refund for double charge",
    "description": "I was charged twice for my subscription. I need a refund for the duplicate payment.",
    "category": "other",
    "priority": "low",
    "auto_classify": true
  }'
# Response: category="billing_question", priority="medium" (classifier overrides)
```
