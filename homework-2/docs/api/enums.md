# Enum Values

> Related: [README.md](README.md) · [models.md](models.md) · [endpoints.md](endpoints.md)

All enum fields are case-sensitive strings. Passing an unlisted value returns a `422` with a message listing the allowed options.

---

## Category

Used on: `Ticket.category`, `TicketCreate.category`, filter `?category=`

| Value | Meaning |
|-------|---------|
| `account_access` | Login problems, password reset, 2FA issues, account lockout |
| `technical_issue` | Bugs, errors, crashes, slow performance, integration failures |
| `billing_question` | Payments, invoices, subscriptions, refunds, pricing questions |
| `feature_request` | Enhancement ideas, new functionality suggestions |
| `bug_report` | Confirmed defects with reproduction steps |
| `other` | Anything that doesn't fit the categories above |

---

## Priority

Used on: `Ticket.priority`, `TicketCreate.priority`, filter `?priority=`

| Value | When to Use |
|-------|-------------|
| `urgent` | Production down, security incident, complete account lockout |
| `high` | Important blocker, customer escalation, ASAP resolution needed |
| `medium` | Normal issue — the default when `priority` is omitted |
| `low` | Minor inconvenience, cosmetic bug, non-urgent suggestion |

---

## Status

Used on: `Ticket.status`, `TicketUpdate.status`, filter `?status=`

| Value | Meaning |
|-------|---------|
| `new` | Ticket created, not yet picked up by an agent |
| `in_progress` | An agent is actively working on it |
| `waiting_customer` | Waiting for more information from the customer |
| `resolved` | Fix applied — `resolved_at` is automatically stamped |
| `closed` | Archived, no further action needed |

> Setting status to `resolved` via `PUT /tickets/{id}` automatically sets `resolved_at` to the current UTC time.

---

## Source (`metadata.source`)

Used on: `TicketMetadata.source`  
Defaults to `api` when not provided.

| Value | Channel |
|-------|---------|
| `web_form` | Customer submitted via the support form on the website |
| `email` | Ticket created from an inbound support email |
| `api` | Created programmatically via the REST API |
| `chat` | Live chat session escalated to a ticket |
| `phone` | Phone call logged as a ticket |

---

## Device Type (`metadata.device_type`)

Used on: `TicketMetadata.device_type`  
Optional — `null` when not provided.

| Value | Meaning |
|-------|---------|
| `desktop` | Desktop or laptop browser |
| `mobile` | Mobile phone |
| `tablet` | Tablet device |
