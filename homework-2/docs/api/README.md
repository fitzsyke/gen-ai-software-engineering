# API Reference

> Customer Support Ticket Management API — Phase 1
>
> Related: [../../README.md](../../README.md) · [../../HOWTORUN.md](../../HOWTORUN.md) · [../architecture/README.md](../architecture/README.md)

**Base URL:** `http://localhost:8000`  
**Interactive docs (Swagger UI):** `http://localhost:8000/docs`  
**Content-Type:** `application/json` — except file uploads, which use `multipart/form-data`

---

## Endpoints

| Method | Path | Description | Success |
|--------|------|-------------|---------|
| `POST` | `/tickets` | Create a new ticket | `201` |
| `POST` | `/tickets/import` | Bulk import from CSV / JSON / XML | `201` / `207` |
| `GET` | `/tickets` | List all tickets (filterable) | `200` |
| `GET` | `/tickets/{id}` | Get a specific ticket | `200` |
| `PUT` | `/tickets/{id}` | Partial update a ticket | `200` |
| `DELETE` | `/tickets/{id}` | Delete a ticket | `204` |
| `GET` | `/health` | Server health check | `200` |

---

## In This Section

| File | Contents |
|------|----------|
| [models.md](models.md) | Request/response schemas — Ticket, TicketCreate, TicketUpdate, ImportSummary |
| [endpoints.md](endpoints.md) | Per-endpoint details, request bodies, responses, and cURL examples |
| [errors.md](errors.md) | Error codes, response shapes, and common error messages |
| [enums.md](enums.md) | All allowed enum values with descriptions |

---

## Quick Examples

```bash
# Create a ticket
curl -s -X POST http://localhost:8000/tickets \
  -H "Content-Type: application/json" \
  -d '{"customer_id":"c1","customer_email":"alice@example.com","customer_name":"Alice","subject":"Cannot log in","description":"Unable to access my account since yesterday.","category":"account_access","priority":"urgent"}'

# Import from CSV
curl -s -X POST http://localhost:8000/tickets/import -F "file=@demo/sample_tickets.csv"

# List urgent new tickets
curl -s "http://localhost:8000/tickets?priority=urgent&status=new"
```
