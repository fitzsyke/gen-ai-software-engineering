# CLAUDE.md — Project Instructions for Claude Code

> This file is read automatically by Claude Code when working in this directory.
> It defines project conventions, architecture rules, and agent behavior for
> the **Customer Support Ticket Management System**.

---

## 🧠 Agent Reasoning Rules

These rules apply to every task in this project, regardless of scope.

### Think Step by Step

Before writing any code or making any change, reason through the problem explicitly:

1. **What** is being asked? (restate it in your own words)
2. **Where** does the change belong in the layer hierarchy?
3. **What** already exists that can be reused?
4. **What** could go wrong? (edge cases, side effects)
5. **How** will you verify it worked?

Do not skip to implementation. The quality of the plan determines the quality of the code.

### Check Your Work

After every change, verify it before reporting it as done:

- **Code changes:** Import the module (`python3 -c "from src.X import Y"`), run the server, make a real request
- **Import changes:** Run the actual import against all three demo files; confirm counts match
- **Model changes:** Create a ticket with the changed field; confirm it round-trips correctly
- **Documentation changes:** Read the rendered output and confirm all links resolve

A change is not done until it is verified. If verification fails, fix it before moving on.

### Show Your Chain of Thought

When solving non-trivial problems, explain your reasoning before presenting the solution:

```
Problem: Empty device_type CSV cells are failing validation.

Chain of thought:
  1. CSV has no concept of null — missing values become empty strings ""
  2. DeviceType is an Optional[DeviceType] enum — it accepts None, not ""
  3. The fix must happen before Pydantic validation, in the normalization pipeline
  4. _normalize_empty_strings() already exists for this purpose
  5. But it runs after _normalize_tags() — and tags needs "" → [] not "" → None
  6. Fix: ensure _normalize_empty_strings() runs FIRST, and _normalize_tags()
     converts None → [] instead of skipping None values

Solution: reorder pipeline + update _normalize_tags() to handle None input.
```

This makes it easier to catch incorrect reasoning before it becomes incorrect code.

### Ask Clarifying Questions When You Lack Information

Do not assume. If a requirement is ambiguous, ask before implementing:

- **Scope unclear?** Ask which phase/task the change belongs to
- **Behavior undefined?** Ask for the expected output on edge cases
- **Conflicting constraints?** Surface the conflict and ask which wins
- **Breaking change?** Ask if backward compatibility is required

State what you know, what you don't know, and what assumption you would make if forced — then ask which is correct.

---

## Project Context

**What this is:** A REST API (Phase 1 of 3) for managing support tickets.
**Stack:** Python 3.11+ / FastAPI / Pydantic v2 / Uvicorn
**Storage:** In-memory thread-safe dict (no database in Phase 1)
**Docs:** See [docs/PLAN.md](docs/PLAN.md) for full architecture. See [AGENTS.md](AGENTS.md) for agent workflow rules.

---

## Running the Project

```bash
# Install dependencies
pip install -r requirements.txt

# Start development server (auto-reloads on changes)
uvicorn src.main:app --reload

# Run from homework-2/ — module path src.main requires it as the working directory
```

**Health check:** `curl http://localhost:8000/health`
**Interactive docs:** `http://localhost:8000/docs`

---

## Architecture Rules

### Layered Architecture — Strict Separation

```
Router  →  Service  →  Storage
```

| Layer | Location | Responsibility | Must NOT |
|-------|----------|----------------|---------|
| **Router** | `src/routers/` | HTTP parsing, status codes, error responses | Contain business logic |
| **Service** | `src/services/` | Business logic, validation, import parsing | Know about HTTP or storage internals |
| **Storage** | `src/storage/` | Data persistence, thread safety | Know about business rules |
| **Models** | `src/models/` | Pydantic models, enums, validators | Import from routers or services |

**Rule:** If you add business logic, it goes in a service. If you add a new HTTP endpoint, it goes in a router that calls a service. Never put queries directly in route handlers.

### Module Singleton Pattern

```python
# Always import the module-level singleton — never instantiate TicketStore() directly
from src.storage.ticket_store import store
```

### Pydantic v2 API — Not v1

| ✅ v2 (correct) | ❌ v1 (wrong) |
|-----------------|--------------|
| `model.model_dump()` | `model.dict()` |
| `model.model_copy(update=...)` | `model.copy(update=...)` |
| `@field_validator` | `@validator` |
| `model_config = ConfigDict(...)` | `class Config:` |
| `model.model_dump(mode="json")` | `model.json()` |

---

## Code Style

### Comments — Clear and User-Friendly

- **File docstrings:** What the file does, what it contains, how other files use it
- **Function docstrings:** What + why (not how). Include key side effects and edge behaviour
- **Inline comments:** Explain non-obvious decisions, not obvious code
- **Section dividers:** `# ── Section Name ──────` for logical groupings

### Error Messages — Human-Readable and Actionable

```python
# ✅ Good — tells the consumer what to fix
raise ValueError(
    "JSON must be either:\n"
    "  • A top-level array: [ {...}, ... ]\n"
    "  • An envelope object: { \"tickets\": [ {...}, ... ] }"
)

# ❌ Bad — not actionable
raise ValueError("Invalid JSON structure")
```

---

## Import Normalization Rules

The 3-step normalization pipeline in `import_service.py` **must run in this order:**

1. `_normalize_empty_strings` — `""` → `None` (must be first; Optional fields need None)
2. `_normalize_tags` — string/None → list (must follow step 1; converts None → `[]`)
3. `_normalize_metadata` — flat `metadata.source` keys → nested dict

Do not reorder. When adding new steps, place them in `_normalize_row()` with a comment explaining where in the sequence they belong.

---

## HTTP Status Codes

| Code | When to use |
|------|-------------|
| `201 Created` | POST /tickets, POST /tickets/import (all rows OK) |
| `204 No Content` | DELETE /tickets/:id |
| `207 Multi-Status` | POST /tickets/import when some rows fail |
| `400 Bad Request` | Malformed CSV/JSON/XML file |
| `404 Not Found` | GET/PUT/DELETE on unknown ticket ID |
| `415 Unsupported Media Type` | Upload that is not .csv/.json/.xml |
| `422 Unprocessable Entity` | Pydantic validation failure (auto-generated) |

---

## Ticket Model Constraints

| Field | Rule |
|-------|------|
| `customer_email` | RFC-5322 email (`EmailStr`) |
| `subject` | 1–200 chars, non-blank after strip |
| `description` | 10–2000 chars |
| `customer_id`, `customer_name` | Non-blank after strip |
| `tags` | List of strings; empty strings stripped |
| `id`, `created_at`, `updated_at`, `resolved_at` | **Server-managed — never set by the client** |

---

## Documentation File Length

Files inside the `docs/` folder must stay **under 350–400 lines**. Beyond that, a file becomes hard to navigate and hard to read.

When a doc in `docs/` reaches that limit, split it into a folder:

```
# Before — too long
docs/API_REFERENCE.md   (600 lines)

# After — split into a folder
docs/api/
├── README.md      # Index with links to sub-files
├── models.md      # Data models and schemas
├── endpoints.md   # Endpoint details and examples
├── errors.md      # Error codes and formats
└── enums.md       # Enum value reference
```

**Rules:**
- Every folder must have a `README.md` that acts as the index and links to its files
- Each sub-file should cover one clear topic — not a grab-bag
- Cross-link related files at the top of each document (`Related: ...`)
- Update all existing links when splitting (search for the old filename)

---

## Phase Scope — Do Not Cross

| Phase | Scope |
|-------|-------|
| **Phase 1 (current)** | CRUD + multi-format import |
| **Phase 2** | Auto-classification endpoint (`POST /tickets/:id/auto-classify`) |
| **Phase 3** | Test suite (>85% coverage) |

Do not add database, auth, rate limiting, or pagination unless explicitly working on Phase 2+.

---

## Demo Files

Keep all demo files importable at 100% success rate:
- `demo/sample_tickets.csv` — 15 rows, all enum variants
- `demo/sample_tickets.json` — 7 tickets, nested metadata
- `demo/sample_tickets.xml` — 7 tickets, element arrays

Verify after any model or normalization change:
```bash
curl -s -X POST http://localhost:8000/tickets/import -F "file=@demo/sample_tickets.csv" \
  | python3 -c "import json,sys; d=json.load(sys.stdin); print(f'CSV: {d[\"successful\"]}/{d[\"total\"]}')"
```
