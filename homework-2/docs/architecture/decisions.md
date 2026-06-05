# Design Decisions

> Related: [README.md](README.md) · [data-flow.md](data-flow.md) · [../PLAN.md](../PLAN.md)

Why things are built the way they are — and what will change in later phases.

---

## Key Decisions

### FastAPI over Flask

| | FastAPI | Flask |
|-|---------|-------|
| Validation | Built-in via Pydantic — zero boilerplate | Manual or via extension |
| Docs | Auto-generated OpenAPI at `/docs` | Requires flask-restx or similar |
| Type safety | Full — request/response types checked | Limited |
| Async | Native | Requires async extensions |

**Decision:** FastAPI. The auto-generated `/docs` UI alone removes the need for a separate API reference tool during development.

---

### In-Memory Store over a Database

**Why for Phase 1:**
- Zero setup — `pip install` is the only step to get running
- Forces a clean storage abstraction (the store interface would be the same for a DB)
- Fast iteration during design — no migrations when models change

**Trade-off:** All tickets are lost on server restart.

**Plan for Phase 2+:** Swap `ticket_store.py` for a SQLite or PostgreSQL implementation. The service layer calls `store.add()`, `store.get()`, etc. — those method signatures won't change, so the rest of the codebase is unaffected.

---

### Dict over List for Storage

```python
# Dict — O(1) lookup by UUID
self._store: Dict[str, Ticket] = {}
ticket = self._store.get(ticket_id)   # instant

# List — O(n) lookup (rejected)
tickets = []
ticket = next((t for t in tickets if str(t.id) == ticket_id), None)  # scans all
```

**Decision:** Dict keyed by UUID string. At any realistic support ticket scale, O(1) vs O(n) matters for GET and DELETE. The cost is slightly higher memory usage, which is irrelevant for Phase 1 volumes.

---

### threading.Lock on Writes Only

FastAPI routes are async but can run in threads (especially with `--workers`). All three write operations (`add`, `update`, `delete`) acquire a `threading.Lock`. Reads do not lock, except `all()` which takes a snapshot copy under the lock.

**Why not lock reads?**
- `dict.get()` is atomic in CPython (GIL)
- `all()` copies the dict values under the lock — callers iterate the copy, not the live dict

**Trade-off:** Not safe for multi-process deployments. Phase 2 database will replace this entirely.

---

### Pydantic v2 Field Validators

Validation lives exclusively in `src/models/ticket.py` — not scattered across services or routes. This means:
- A ticket created via `POST /tickets` gets the same validation as a row imported from CSV
- Adding a new constraint requires changing one file

The import service normalises raw file data (empty strings, flat keys, tag strings) *before* handing it to Pydantic, so the models stay clean and format-agnostic.

---

### 207 Multi-Status for Partial Import

On bulk import, some rows may succeed and others fail. Returning `400` would be misleading (some data *was* saved). Returning `201` would hide the failures. `207 Multi-Status` is the correct HTTP signal for "partial success on a batch operation."

The full `ImportSummary` is returned regardless of status code — the client always has complete information.

---

### Import Normalisation Pipeline (Ordered)

The three-step pipeline in `_normalize_row()` must run in this specific order:

```
1. _normalize_empty_strings   ""  → None
2. _normalize_tags            None/string → list
3. _normalize_metadata        flat keys → nested dict
```

Step 1 must precede step 2 because step 2 converts `None` → `[]` for tags — if step 2 ran first on a raw `""`, it would try to call `.split(",")` on an empty string and produce `[""]` instead of `[]`.

---

## What's Not Here (Phase 2+)

| Feature | Phase | Reason not in Phase 1 |
|---------|-------|----------------------|
| **Database** | 2 | Would add setup friction; in-memory validates the architecture first |
| **Auto-classification** | 2 | Separate concern — keyword matching + confidence scoring |
| **Authentication** | 2+ | Not required for the homework scope |
| **Pagination** | 2+ | In-memory filtering is fast enough at demo scale |
| **Rate limiting** | 2+ | Not required for single-user development |
| **Test suite** | 3 | Dedicated task with >85% coverage target |
