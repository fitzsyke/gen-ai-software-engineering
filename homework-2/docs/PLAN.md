# 📐 Implementation Plan: Phase 1 — Multi-Format Ticket Import API

**Status:** ✅ **Phase 1 Complete** · ✅ **Phase 2 Complete** · ✅ **Phase 3 Complete**  
**Phase 1 Date:** May 24, 2026  
**Phase 2 Date:** May 26, 2026  
**Phase 3 Date:** May 28, 2026  
**Framework:** FastAPI + Pydantic v2 (Python)  
**Storage:** In-memory thread-safe dict

---

## Context

This document outlines the Phase 1 implementation for the **Customer Support Ticket Management System**. Phase 1 focuses on building a solid foundation: a clean REST API that handles full CRUD operations, multi-format bulk imports (CSV, JSON, XML), and filtered ticket listing.

### Why This Architecture?

- **FastAPI** chosen over Flask for built-in Pydantic validation, auto-generated OpenAPI docs (`/docs`), and type safety throughout
- **In-memory storage** for Phase 1 keeps setup frictionless (one `pip install`, no database config)
- **Layered architecture** (Router → Service → Storage) makes components testable and swappable
- **Threading lock** on store writes ensures concurrent requests are safe

Phase 2 will add auto-classification; Phase 3 will add comprehensive test coverage — this architecture supports both without touching the current codebase.

---

## Folder Structure

```
homework-2/
├── src/
│   ├── __init__.py
│   ├── main.py                        # FastAPI app, middleware, router registration
│   ├── models/
│   │   ├── __init__.py
│   │   └── ticket.py                  # Pydantic models + enums + validators
│   ├── routers/
│   │   ├── __init__.py
│   │   └── tickets.py                 # Route handlers (thin delegates)
│   ├── services/
│   │   ├── __init__.py
│   │   ├── ticket_service.py          # CRUD business logic
│   │   └── import_service.py          # CSV/JSON/XML parsing + normalization
│   └── storage/
│       ├── __init__.py
│       └── ticket_store.py            # Thread-safe in-memory store singleton
├── demo/
│   ├── sample_tickets.csv             # 15 tickets, all enum variants covered
│   ├── sample_tickets.json            # 7 tickets, nested metadata
│   └── sample_tickets.xml             # 7 tickets, repeated element arrays
├── docs/
│   ├── PLAN.md                        # This file
│   ├── API_REFERENCE.md               # Endpoint docs with cURL examples
│   └── ARCHITECTURE.md                # Mermaid diagrams + design decisions
├── requirements.txt
├── README.md
├── HOWTORUN.md
└── TASKS.md
```

---

## Implementation Details

### 1. Core Models (`src/models/ticket.py`)

**Enums** — all inherit from `str, Enum` for clean JSON serialization:
- `Category`: account_access, technical_issue, billing_question, feature_request, bug_report, other
- `Priority`: urgent, high, medium, low
- `Status`: new, in_progress, waiting_customer, resolved, closed
- `Source`: web_form, email, api, chat, phone
- `DeviceType`: desktop, mobile, tablet

**Pydantic Models:**
- `TicketMetadata(BaseModel)` — source, browser, device_type
- `TicketCreate(BaseModel)` — request body with validators for subject (1-200 chars), description (10-2000 chars), email validation
- `TicketUpdate(BaseModel)` — all Optional fields for partial PUT updates
- `Ticket(TicketCreate)` — full stored object with id, status, timestamps
- `ImportError(BaseModel)` — row number, raw data, error messages for bulk import reporting
- `ImportSummary(BaseModel)` — total, successful, failed, tickets, errors
- `FilterParams(BaseModel)` — query parameter container for GET /tickets

### 2. Storage Layer (`src/storage/ticket_store.py`)

**TicketStore class:**
- `_store: Dict[str, Ticket]` — UUID string key → Ticket value
- `_lock: threading.Lock` — protects all writes (add, update, delete)
- Methods: `add()`, `get()`, `all()` (snapshot), `update()`, `delete()`, `count()`

**Module singleton:**
```python
store = TicketStore()  # Shared across all app layers
```

### 3. Service Layer

#### `src/services/ticket_service.py` — CRUD Logic

- `create_ticket(data: TicketCreate) → Ticket` — stamps UUID + timestamps
- `get_ticket(id) → Optional[Ticket]`
- `list_tickets(filters: FilterParams) → List[Ticket]` — AND filter logic, newest-first sort
- `update_ticket(id, data: TicketUpdate) → Optional[Ticket]` — auto-stamps `resolved_at` when status → resolved
- `delete_ticket(id) → bool`

#### `src/services/import_service.py` — Multi-Format Parsing

All three parsers funnel rows through `_validate_and_create_row()` so validation logic is centralized.

**CSV (`import_csv`)**:
- `utf-8-sig` decoding handles Excel BOM
- `csv.DictReader` — headers must match Ticket field names
- Tags: comma-split quoted cells `"billing,refund"` → `["billing", "refund"]`
- Metadata: flat headers `metadata.source`, `metadata.device_type` → nested dict

**JSON (`import_json`)**:
- Accepts bare array `[...]` OR envelope `{"tickets": [...]}`
- Detailed error messages with line/column info on parse failures

**XML (`import_xml`)**:
- Root `<tickets>`, children `<ticket>`
- Nested `<metadata><source>…</source></metadata>` → flattened dict
- Tags: supports both comma string and repeated child elements

**Return:** `ImportSummary` with HTTP 201 (all OK), 207 (mixed), or 400 (unparseable file)

**Normalization pipeline:**
1. Empty strings → None (so Optional fields work correctly)
2. Tags strings → lists
3. Flat metadata keys → nested dict

### 4. Router Layer (`src/routers/tickets.py`)

Thin handlers — all delegate to services. HTTP concerns only (status codes, error responses).

| Method | Path | Handler | Status |
|--------|------|---------|--------|
| POST | /tickets | create_ticket | 201 |
| POST | /tickets/import | import_tickets | 201/207/400/415 |
| GET | /tickets | list_tickets | 200 |
| GET | /tickets/{id} | get_ticket | 200/404 |
| PUT | /tickets/{id} | update_ticket | 200/404 |
| DELETE | /tickets/{id} | delete_ticket | 204/404 |

### 5. App Entry (`src/main.py`)

- FastAPI instance with OpenAPI metadata
- CORS middleware (allow all for demo)
- Global exception handler → JSON 500 (not HTML)
- Router registration
- `/health` endpoint for smoke tests

---

## Demo Files

All tested and verified to import successfully:

| File | Format | Records | Coverage |
|------|--------|---------|----------|
| `demo/sample_tickets.csv` | CSV | 15 | All categories, priorities, statuses, metadata variants |
| `demo/sample_tickets.json` | JSON | 7 | Nested metadata, all enums, tags |
| `demo/sample_tickets.xml` | XML | 7 | Nested elements, repeated tag arrays |

---

## Error Handling

### Validation Errors (422 Unprocessable Entity)
FastAPI/Pydantic auto-generates structured errors:
```json
{
  "detail": [
    {
      "type": "string_too_short",
      "loc": ["body", "description"],
      "msg": "Value error, description is too short (5 chars); min is 10",
      "input": "short"
    }
  ]
}
```

### Application Errors (400, 404, 415, 500)
```json
{
  "detail": "Ticket 'uuid...' not found"
}
```

### Bulk Import Errors (207 Multi-Status)
```json
{
  "total": 10,
  "successful": 8,
  "failed": 2,
  "tickets": [...],
  "errors": [
    {
      "row": 3,
      "raw_data": {...},
      "errors": ["customer_email: value is not a valid email address"]
    }
  ]
}
```

---

## Implementation Sequence (Used)

1. ✅ `requirements.txt` — dependencies
2. ✅ `src/models/ticket.py` — all Pydantic models + enums
3. ✅ `src/storage/ticket_store.py` — store singleton
4. ✅ `src/services/ticket_service.py` — CRUD logic
5. ✅ `src/routers/tickets.py` — route handlers
6. ✅ `src/main.py` — app wiring
7. ✅ `src/services/import_service.py` — all three parsers
8. ✅ `demo/` files — CSV, JSON, XML samples
9. ⏳ `docs/API_REFERENCE.md` — endpoint documentation
10. ⏳ `docs/ARCHITECTURE.md` — design decision docs

---

## Verification Results

### ✅ Server Startup
```
INFO: Started server process [63461]
INFO: Application startup complete
```

### ✅ Health Check
```json
{"status": "ok", "ticket_count": 0, "version": "1.0.0"}
```

### ✅ Create Ticket (POST /tickets)
- Returns 201 with full ticket + UUID + timestamps
- Validates email format
- Validates subject length (1-200 chars)
- Validates description length (10-2000 chars)

### ✅ Validation Errors (422)
- Empty description → clear error message
- Invalid enum → lists allowed values

### ✅ Bulk Import
- **CSV:** 15 rows imported successfully (100%)
- **JSON:** 7 rows imported successfully (100%)
- **XML:** 7 rows imported successfully (100%)
- **Total:** 29 tickets in store

### ✅ Filtering
- `?priority=urgent` → 7 tickets
- `?status=new` → All 29 tickets
- `?category=billing_question` → 6 tickets
- Newest-first sort confirmed

### ✅ GET Single Ticket (GET /tickets/:id)
- Returns full ticket object
- 404 on missing ID

### ✅ Update Ticket (PUT /tickets/:id)
- Partial update works
- Setting status=resolved auto-stamps `resolved_at`
- 404 on missing ID

### ✅ Delete Ticket (DELETE /tickets/:id)
- Returns 204 No Content
- Subsequent GET returns 404

### ✅ Error Handling
- 415 Unsupported Media Type for non-.csv/.json/.xml files
- 422 for invalid enum filter values
- Clear error messages

---

## Design Decisions

| Decision | Rationale | Trade-off |
|----------|-----------|-----------|
| **In-memory store** | Zero setup, fast iteration | Lost on restart; Phase 2 adds DB |
| **Layered architecture** | Easy to test, swap storage | Slight overhead vs monolith |
| **threading.Lock** | Safe concurrent access | Not distributed; one-server only |
| **Pydantic v2** | Type-safe, auto-validation | Requires Python 3.11+ |
| **FastAPI** | Async, OpenAPI built-in | Less minimal than Flask |

---

## Phase 2: Auto-Classification ✅

| Feature | Implementation |
|---------|---------------|
| `POST /tickets/:id/auto-classify` | New endpoint; runs classification on any existing ticket |
| `auto_classify: bool` on `TicketCreate` | Pass `true` to classify at creation time; works in bulk import too |
| Keyword-based scoring | `classify_service.py` — keyword dicts for each `Category` and `Priority` |
| Confidence scoring | Dominance ratio: `best_hits / total_hits`; tied → `other` with low confidence |
| Stored on ticket | `classification: ClassificationResult` field on `Ticket` model |
| Re-classifiable | Calling the endpoint again replaces the previous result |
| Updates category + priority | Classification overwrites submitted values; response shows the final state |

### New file: `src/services/classify_service.py`
- `classify(subject, description) → ClassificationResult` — pure function, no side effects
- `_score_text()` — keyword hit counting per label
- `_pick_best()` — dominance ratio + tie-breaking to "other"
- `_collect_matched_keywords()` — deduped list of all found keywords

### Model additions (`src/models/ticket.py`)
- `ClassificationResult(BaseModel)` — category, category_confidence, priority, priority_confidence, matched_keywords, classified_at
- `auto_classify: bool = False` on `TicketCreate` (request flag, not stored)
- `classification: Optional[ClassificationResult] = None` on `Ticket`

---

## Phase 3: Test Suite ✅

| Metric | Result |
|--------|--------|
| Total tests | 144 |
| Overall coverage | **98%** (target: >85%) |
| Test runner | pytest 8.x + pytest-cov |
| Test files | 9 files across `tests/` |

### Test files
- `test_ticket_api.py` — 37 API endpoint tests (all routes, status codes, filters)
- `test_ticket_model.py` — 21 Pydantic validator unit tests
- `test_import_csv.py` — 13 CSV parser tests (BOM, tags, metadata, errors)
- `test_import_json.py` — 10 JSON parser tests (array + envelope format, errors)
- `test_import_xml.py` — 9 XML parser tests (tag arrays, nested metadata, errors)
- `test_categorization.py` — 18 classifier unit tests (all categories, scoring)
- `test_integration.py` — 6 end-to-end workflow tests (lifecycle, concurrent)
- `test_performance.py` — 7 benchmark tests (time budgets, throughput)
- `test_edge_cases.py` — 23 targeted edge case tests

### Bug fixed during test writing
- **XML single-child element bug:** `_xml_element_to_dict` incorrectly treated single-child elements as arrays (e.g. `<metadata><source>email</source></metadata>` → `["email"]`). Fixed by requiring more than one child element to trigger array mode.
- **Empty metadata normalization:** `_normalize_metadata` now skips `None` values so empty CSV metadata cells use Pydantic field defaults instead of failing validation.

---

## What's Not in This Project

- ❌ Pagination on GET /tickets
- ❌ Authentication/authorization
- ❌ Persistent storage (database)
- ❌ Rate limiting
- ❌ Request logging

---

*For setup and running instructions, see [HOWTORUN.md](../HOWTORUN.md).*  
*For API endpoint details, see [api/README.md](api/README.md).*  
*For architecture deep-dive, see [architecture/README.md](architecture/README.md).*
