# Data Flow

> Related: [README.md](README.md) · [decisions.md](decisions.md) · [../api/endpoints.md](../api/endpoints.md)

Sequence diagrams for the two most complex flows in Phase 1.

---

## POST /tickets/import — Bulk Import Flow

The import endpoint is the most complex path: it parses a file, normalises each row, validates it, and persists the successes — all while collecting errors for the failures.

```mermaid
sequenceDiagram
    actor Client
    participant Router as Router<br/>tickets.py
    participant Import as ImportService<br/>import_service.py
    participant Tickets as TicketService<br/>ticket_service.py
    participant Store as TicketStore<br/>ticket_store.py

    Client->>Router: POST /tickets/import<br/>multipart/form-data (file)

    Router->>Router: read file bytes<br/>detect format from extension

    alt Unsupported extension
        Router-->>Client: 415 Unsupported Media Type
    end

    Router->>Import: import_csv/json/xml(content)

    Import->>Import: parse bytes → raw rows[]<br/>(csv.DictReader / json.loads / ET.fromstring)

    alt File is malformed
        Import-->>Router: raises ValueError
        Router-->>Client: 400 Bad Request
    end

    loop For each row
        Import->>Import: _normalize_row(row)<br/>1. empty strings → None<br/>2. tags string → list<br/>3. flat metadata keys → nested dict

        Import->>Tickets: create_ticket(TicketCreate(**row))

        alt Validation passes
            Tickets->>Tickets: stamp UUID + timestamps
            Tickets->>Store: store.add(ticket)
            Store-->>Tickets: Ticket
            Tickets-->>Import: Ticket ✓
            Import->>Import: append to tickets[]
        else Validation fails (ValidationError)
            Import->>Import: append to errors[]<br/>{row, raw_data, messages}
        end
    end

    Import-->>Router: ImportSummary{total, successful, failed, tickets, errors}

    alt All succeeded
        Router-->>Client: 201 Created + ImportSummary
    else Mixed results
        Router-->>Client: 207 Multi-Status + ImportSummary
    end
```

---

## PUT /tickets/{id} — Ticket Update Flow

Demonstrates the partial-update pattern and the `resolved_at` auto-stamp behaviour.

```mermaid
sequenceDiagram
    actor Client
    participant Router as Router<br/>tickets.py
    participant Service as TicketService<br/>ticket_service.py
    participant Store as TicketStore<br/>ticket_store.py

    Client->>Router: PUT /tickets/{id}<br/>JSON body (TicketUpdate)

    Router->>Router: validate UUID path param<br/>validate TicketUpdate body (Pydantic)

    alt Invalid UUID or body
        Router-->>Client: 422 Unprocessable Entity
    end

    Router->>Service: update_ticket(id, TicketUpdate)

    Service->>Store: store.get(id)
    Store-->>Service: existing Ticket (or None)

    alt Ticket not found
        Service-->>Router: None
        Router-->>Client: 404 Not Found
    end

    Service->>Service: changes = data.model_dump(exclude_none=True)

    alt status == "resolved" AND resolved_at is None
        Service->>Service: changes["resolved_at"] = now (UTC)
        Note over Service: First-resolve only — timestamp preserved on re-resolve
    end

    Service->>Service: changes["updated_at"] = now (UTC)
    Service->>Service: updated = existing.model_copy(update=changes)

    Service->>Store: store.update(id, updated)
    Store-->>Service: updated Ticket

    Service-->>Router: updated Ticket
    Router-->>Client: 200 OK + updated Ticket
```

---

## POST /tickets — Simple Create Flow

Included for completeness — the straightforward path.

```mermaid
sequenceDiagram
    actor Client
    participant Router as Router<br/>tickets.py
    participant Service as TicketService<br/>ticket_service.py
    participant Store as TicketStore<br/>ticket_store.py

    Client->>Router: POST /tickets<br/>JSON body (TicketCreate)

    Router->>Router: validate body (Pydantic)

    alt Validation fails
        Router-->>Client: 422 Unprocessable Entity
    end

    Router->>Service: create_ticket(TicketCreate)
    Service->>Service: stamp UUID, created_at, updated_at<br/>set status = "new"
    Service->>Store: store.add(ticket)
    Store-->>Service: Ticket
    Service-->>Router: Ticket
    Router-->>Client: 201 Created + Ticket
```
