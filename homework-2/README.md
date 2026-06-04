# 🎧 Homework 2: Intelligent Customer Support System

> **Student Name**: Artem Saienko
> **Date Submitted**: 31.05.2026
> **AI Tools Used**: Claude Code (Sonnet 4.6, Haiku 4.5)

> **Phase 1 & 2 Complete** — Multi-format ticket import API + keyword-based auto-classification

**Status:** ✅ Task 1 · ✅ Task 2 · ✅ Task 3 — All phases complete  
**Coverage:** 98% · **Tests:** 144 passing

---

## 📋 Project Overview

Build a customer support ticket management system that imports tickets from multiple file formats, automatically categorizes issues, and assigns priorities using the **Context-Model-Prompt framework** and AI-assisted development.

### ✨ What's Built

**Phase 1 — Multi-Format Ticket Import API:**
- ✅ **Full REST API** — POST, GET, PUT, DELETE for tickets
- ✅ **Multi-format import** — CSV, JSON, XML with per-row error reporting
- ✅ **Smart filtering** — by status, category, priority, assignee, tags
- ✅ **Auto-stamping** — `resolved_at` set automatically when status → resolved
- ✅ **Validation** — email format, string length constraints, enum validation
- ✅ **Thread-safe** — concurrent requests safe on in-memory store
- ✅ **Interactive docs** — OpenAPI UI at `/docs`, zero config

**Phase 2 — Auto-Classification:**
- ✅ **`POST /tickets/:id/auto-classify`** — classify any existing ticket on demand
- ✅ **`auto_classify: true`** flag on ticket creation (single or bulk import)
- ✅ **Keyword scoring** — per-category and per-priority keyword dictionaries
- ✅ **Confidence scores** — dominance ratio, tied labels fall back to "other"/"medium"
- ✅ **Stored on ticket** — `classification` field holds the full result
- ✅ **Re-classifiable** — calling auto-classify again replaces the previous result

---

## 🚀 Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Start the server
uvicorn src.main:app --reload

# 3. Open the interactive API docs
open http://localhost:8000/docs

# 4. Or test with cURL (see HOWTORUN.md for examples)
curl -X POST http://localhost:8000/tickets/import -F "file=@demo/sample_tickets.csv"
```

---

## 📚 Documentation Map

| Document | Audience | Contents |
|----------|----------|----------|
| **[HOWTORUN.md](HOWTORUN.md)** | Everyone | Step-by-step setup + copy-paste cURL examples for every endpoint |
| **[docs/api/](docs/api/README.md)** | API consumers | Endpoints, request/response schemas, error codes, enum values |
| **[docs/architecture/](docs/architecture/README.md)** | Tech leads | Architecture diagrams (Mermaid), data flow, design decisions |
| **[docs/TESTING_GUIDE.md](docs/TESTING_GUIDE.md)** | QA engineers | Test pyramid, how to run, coverage report, benchmarks |
| **[docs/PLAN.md](docs/PLAN.md)** | Architects | Implementation strategy, phase status, verification results |
| **[TASKS.md](TASKS.md)** | Students | Original assignment specification (Task 1, 2, 3) |

---

## 🏗️ Architecture

```
HTTP Client (browser / curl / SDK)
        ↓
    Router Layer (routers/tickets.py)
        ↓
    Service Layer (services/ticket_service.py + import_service.py)
        ↓
    Storage Layer (storage/ticket_store.py)
        ↓
    In-Memory Dict with threading.Lock
```

**Why this design?**
- Router handles HTTP (parsing, status codes, errors)
- Service handles business logic (CRUD, import parsing, validation)
- Storage handles data persistence (in-memory now, DB later)
- Clear separation → easier to test, swap, extend

---

## 📡 API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/tickets` | Create a new ticket |
| `POST` | `/tickets/import` | Bulk import CSV/JSON/XML |
| `GET` | `/tickets` | List all tickets (filterable) |
| `GET` | `/tickets/{id}` | Get a specific ticket |
| `PUT` | `/tickets/{id}` | Update a ticket (partial) |
| `DELETE` | `/tickets/{id}` | Delete a ticket |
| `POST` | `/tickets/{id}/auto-classify` | Run keyword-based auto-classification |
| `GET` | `/health` | Server health check |

**Examples:**
```bash
# Create a ticket
curl -X POST http://localhost:8000/tickets \
  -H "Content-Type: application/json" \
  -d '{"customer_id":"c1","customer_email":"alice@example.com","customer_name":"Alice","subject":"Cannot log in","description":"I cannot access my account since yesterday.","category":"account_access","priority":"urgent"}'

# List urgent tickets
curl "http://localhost:8000/tickets?priority=urgent"

# Import from CSV
curl -X POST http://localhost:8000/tickets/import -F "file=@demo/sample_tickets.csv"
```

Full endpoint docs → [docs/API_REFERENCE.md](docs/API_REFERENCE.md)

---

## 🧪 Demo Data

Pre-built sample files for testing:

| File | Format | Records | Use Case |
|------|--------|---------|----------|
| `demo/sample_tickets.csv` | CSV | 15 tickets | Test CSV parsing, all enum variants |
| `demo/sample_tickets.json` | JSON | 7 tickets | Test JSON import, nested metadata |
| `demo/sample_tickets.xml` | XML | 7 tickets | Test XML parsing, element arrays |

**Import them:**
```bash
# All three should import 100% successfully
curl -X POST http://localhost:8000/tickets/import -F "file=@demo/sample_tickets.csv"
curl -X POST http://localhost:8000/tickets/import -F "file=@demo/sample_tickets.json"
curl -X POST http://localhost:8000/tickets/import -F "file=@demo/sample_tickets.xml"
```

---

## 📊 Ticket Model

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "customer_id": "cust-001",
  "customer_email": "alice@example.com",
  "customer_name": "Alice Johnson",
  "subject": "Cannot log into my account",
  "description": "I have been unable to log in since yesterday...",
  "category": "account_access",
  "priority": "urgent",
  "status": "new",
  "created_at": "2026-05-24T15:46:13.132462+00:00",
  "updated_at": "2026-05-24T15:46:13.132462+00:00",
  "resolved_at": null,
  "assigned_to": null,
  "tags": ["account", "security"],
  "metadata": {
    "source": "web_form",
    "browser": "Chrome 124",
    "device_type": "desktop"
  }
}
```

---

## 🔧 Tech Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| **Framework** | FastAPI | Built-in async, OpenAPI docs, Pydantic integration |
| **Validation** | Pydantic v2 | Type-safe models, declarative validators, email validation |
| **Storage** | In-memory dict | Zero setup for Phase 1; easy to swap with DB in Phase 2 |
| **Server** | Uvicorn | ASGI, fast, development reload support |
| **Language** | Python 3.11+ | Type hints, modern syntax |

---

## 📁 Project Structure

```
homework-2/
├── src/
│   ├── main.py                    # FastAPI app entry, middleware, routing
│   ├── models/ticket.py           # Pydantic models + enums + validators
│   ├── routers/tickets.py         # HTTP route handlers
│   ├── services/
│   │   ├── ticket_service.py      # CRUD business logic
│   │   └── import_service.py      # CSV/JSON/XML parsing + normalization
│   └── storage/ticket_store.py    # Thread-safe in-memory store
├── demo/
│   ├── sample_tickets.csv         # 15 test tickets
│   ├── sample_tickets.json        # 7 test tickets
│   └── sample_tickets.xml         # 7 test tickets
├── docs/
│   ├── PLAN.md                    # Implementation plan (this phase)
│   ├── API_REFERENCE.md           # Endpoint documentation
│   └── ARCHITECTURE.md            # Architecture & design decisions
├── requirements.txt               # Dependencies
├── README.md                      # This file
├── HOWTORUN.md                    # Setup guide
└── TASKS.md                       # Assignment specification
```

---

## ✅ Verification Checklist

Phase 1 has been fully implemented and tested:

- ✅ Server starts cleanly
- ✅ Health check responds
- ✅ Create ticket endpoint (POST /tickets)
- ✅ Validation errors return 422 with field-level detail
- ✅ CSV import: 15/15 tickets (100%)
- ✅ JSON import: 7/7 tickets (100%)
- ✅ XML import: 7/7 tickets (100%)
- ✅ List tickets with filtering (status, category, priority, tags)
- ✅ Get single ticket (GET /tickets/:id)
- ✅ Update ticket with auto-resolved_at stamping
- ✅ Delete ticket (returns 204)
- ✅ 404 on missing tickets
- ✅ 415 for unsupported file types
- ✅ 422 for invalid enum filters

---

## 🎯 Next Steps

**Phase 3 — Test Suite:** ✅ Complete
- ✅ **98% code coverage** (target >85%)
- ✅ **144 tests** across 9 test files
- ✅ Unit, API, integration, and performance tests
- ✅ `tests/fixtures/` — sample data for all three formats

---

## 🤝 How This Was Built

Using the **Context-Model-Prompt (CMP) framework**:

1. **Context** — Understood the assignment, tech stack options, requirements
2. **Model** — Designed layered architecture, Pydantic data models, import logic
3. **Prompt** — Asked Claude for implementation, iterated on feedback

See [docs/PLAN.md](docs/PLAN.md) for detailed architecture decisions and verification results.

---

<div align="center">

*This project was completed as part of the AI-Assisted Development course, Homework 2.*

**All Phases:** ✅ Complete  
**Lines of Code:** ~1,700 (well-documented)  
**Test Coverage:** 98% · 144 tests passing

</div>
