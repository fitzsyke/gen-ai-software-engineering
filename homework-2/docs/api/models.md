# Data Models

> Related: [README.md](README.md) · [endpoints.md](endpoints.md) · [enums.md](enums.md)

All models are defined in [`src/models/ticket.py`](../../src/models/ticket.py) using Pydantic v2.

---

## Ticket

The full stored object — returned by every endpoint.  
Server-managed fields (`id`, `status`, `created_at`, `updated_at`, `resolved_at`) are never set by the client.

```json
{
  "id":             "550e8400-e29b-41d4-a716-446655440000",
  "customer_id":    "cust-001",
  "customer_email": "alice@example.com",
  "customer_name":  "Alice Johnson",
  "subject":        "Cannot log into my account",
  "description":    "Unable to access my account since yesterday evening...",
  "category":       "account_access",
  "priority":       "urgent",
  "status":         "new",
  "created_at":     "2026-05-24T15:46:13.132462+00:00",
  "updated_at":     "2026-05-24T15:46:13.132462+00:00",
  "resolved_at":    null,
  "assigned_to":    null,
  "tags":           ["account", "security"],
  "metadata": {
    "source":      "web_form",
    "browser":     "Chrome 124",
    "device_type": "desktop"
  }
}
```

| Field | Type | Constraints |
|-------|------|-------------|
| `id` | UUID string | Auto-generated |
| `customer_id` | string | Required, non-blank |
| `customer_email` | string | Required, valid email format |
| `customer_name` | string | Required, non-blank |
| `subject` | string | Required, 1–200 characters |
| `description` | string | Required, 10–2000 characters |
| `category` | enum | Required — see [enums.md](enums.md) |
| `priority` | enum | Required — see [enums.md](enums.md) |
| `status` | enum | Server-managed, starts as `new` |
| `created_at` | ISO 8601 datetime | Server-managed, set at creation |
| `updated_at` | ISO 8601 datetime | Server-managed, updated on every PUT |
| `resolved_at` | ISO 8601 datetime or `null` | Auto-stamped when status → `resolved` |
| `assigned_to` | string or `null` | Optional |
| `tags` | array of strings | Optional, defaults to `[]` |
| `metadata` | object | Optional — see TicketMetadata below |
| `classification` | object or `null` | Set after auto-classify runs — see ClassificationResult below |

---

## TicketMetadata

Embedded in every Ticket. Captures context about how and where the ticket was submitted.

```json
{
  "source":      "web_form",
  "browser":     "Chrome 124",
  "device_type": "desktop"
}
```

| Field | Type | Default |
|-------|------|---------|
| `source` | enum | `api` |
| `browser` | string or `null` | `null` |
| `device_type` | enum or `null` | `null` |

---

## ClassificationResult

Embedded in a Ticket after `POST /tickets/:id/auto-classify` runs (or when a ticket
is created with `"auto_classify": true`). Describes the classifier's decision.

```json
{
  "category":             "billing_question",
  "category_confidence":  0.86,
  "priority":             "medium",
  "priority_confidence":  1.0,
  "matched_keywords":     ["billing", "charge", "invoice", "payment", "refund"],
  "classified_at":        "2026-05-26T10:00:00+00:00"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `category` | enum | Classifier's assigned category (overwrites submitted value) |
| `category_confidence` | float (0–1) | Dominance ratio of keyword hits; <0.5 means few signals |
| `priority` | enum | Classifier's assigned priority (overwrites submitted value) |
| `priority_confidence` | float (0–1) | Dominance ratio for priority keywords |
| `matched_keywords` | array of strings | Every keyword found in subject + description |
| `classified_at` | ISO 8601 datetime | When classification ran |

**Confidence interpretation:**
- `1.0` — All keyword hits were for one label; very strong signal
- `0.5` (no keywords) — No signal; fallback label assigned (`other` / `medium`)
- `0.3` — Tied between two labels; ambiguous, fallback assigned

---

## TicketCreate

Request body for `POST /tickets`. All fields are required except `assigned_to`, `tags`, `metadata`, and `auto_classify`.

```json
{
  "customer_id":    "cust-001",
  "customer_email": "alice@example.com",
  "customer_name":  "Alice Johnson",
  "subject":        "Cannot log into my account",
  "description":    "Unable to access my account since yesterday evening.",
  "category":       "account_access",
  "priority":       "urgent",
  "assigned_to":    null,
  "tags":           ["account", "security"],
  "metadata": {
    "source":      "web_form",
    "browser":     "Chrome 124",
    "device_type": "desktop"
  },
  "auto_classify":  false
}
```

| Field | Default | Notes |
|-------|---------|-------|
| `auto_classify` | `false` | If `true`, classifier runs after creation and overwrites `category` and `priority`. Not stored on the ticket. Works in bulk import rows too. |

---

## TicketUpdate

Request body for `PUT /tickets/{id}`. Every field is optional — only included fields are changed.

```json
{
  "status":      "in_progress",
  "assigned_to": "agent-sarah",
  "priority":    "high",
  "tags":        ["escalated", "billing"]
}
```

> Setting `status` to `resolved` automatically stamps `resolved_at` with the current UTC time.  
> All other field constraints (length, enum values) still apply when a field is provided.

---

## ImportSummary

Response body for `POST /tickets/import`.

```json
{
  "total":      15,
  "successful": 13,
  "failed":     2,
  "tickets":    ["... array of created Ticket objects ..."],
  "errors": [
    {
      "row":      4,
      "raw_data": {"customer_email": "not-an-email", "subject": "Test"},
      "errors":   ["customer_email: value is not a valid email address"]
    }
  ]
}
```

| Field | Type | Description |
|-------|------|-------------|
| `total` | int | Total rows in the uploaded file |
| `successful` | int | Rows that passed validation and were saved |
| `failed` | int | Rows that failed validation |
| `tickets` | array | The newly created Ticket objects |
| `errors` | array | Per-row error details for failed rows |
| `errors[].row` | int | 1-based row number in the source file |
| `errors[].raw_data` | object | The raw parsed row that failed |
| `errors[].errors` | array of strings | Human-readable validation error messages |
