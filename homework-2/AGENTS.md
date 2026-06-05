# AGENTS.md — AI Agent Workflow Guide

> How AI agents (and humans acting as agents) should approach work in this project.
> This complements [CLAUDE.md](CLAUDE.md) (code rules) and [docs/PLAN.md](docs/PLAN.md) (architecture).

---

## Core Philosophy

This project is built using the **Context-Model-Prompt (CMP) framework**:

1. **Context** — Understand the full situation before acting (codebase, constraints, what already exists)
2. **Model** — Design the approach (what changes, in what layer, in what order)
3. **Prompt** — Execute with intention and verify the result

Do not skip Context and jump to code. The most common source of mistakes is acting on an incomplete picture.

---

## Workflow: Every Task

### Phase 1 — Understand Before Acting

Before touching any file:

1. **Read the task description completely.** Identify what is in scope and what is not.
2. **Explore relevant files.** Understand what already exists that can be reused.
3. **Identify the correct layer.** (Router? Service? Model? Storage?)
4. **State your understanding.** Before writing code, summarize what you are going to do and why. This is your chain of thought — make it visible.

**If anything is ambiguous, ask before assuming.** State what you know, what you don't, and what assumption you would make — then ask which is correct.

```
Example of a good clarifying question:
  "The task says 'add filtering by date range' for GET /tickets.
   I'm not sure whether:
   a) filter by created_at only, or
   b) filter by any date field (created_at, updated_at, resolved_at)
   I'd default to created_at. Which is correct?"
```

### Phase 2 — Design the Change

Think step by step through the implementation:

1. Which files will change?
2. In what order should they change? (models first, then services, then routers)
3. What validation or normalization is needed?
4. What edge cases exist?
5. What HTTP status code does this return?
6. How will you verify it?

For non-trivial changes, write the plan before writing the code. A one-paragraph explanation of the approach is enough.

### Phase 3 — Implement

Follow the [build order principle](#build-order): always make the smallest runnable change first, then expand. After each meaningful step, verify the server still starts cleanly.

Commit-sized changes are easier to review and revert than large rewrites.

### Phase 4 — Verify

**A change is not done until it is tested with a real request.**

Minimum verification for any code change:
```bash
# 1. Server starts
uvicorn src.main:app --reload

# 2. Health check responds
curl http://localhost:8000/health

# 3. The affected endpoint behaves correctly
curl -X POST http://localhost:8000/tickets ...

# 4. Demo imports still succeed at 100%
curl -X POST http://localhost:8000/tickets/import -F "file=@demo/sample_tickets.csv"
```

If a test fails, **do not report it as done.** Fix it first.

### Phase 5 — Document

After verifying, update the affected documentation:
- New endpoint? → update [docs/API_REFERENCE.md](docs/API_REFERENCE.md)
- Architecture change? → update [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- New phase started? → update [docs/PLAN.md](docs/PLAN.md) status
- Breaking change? → update [HOWTORUN.md](HOWTORUN.md) examples

---

## Build Order Principle

Always build in a sequence that keeps the system runnable at every step:

```
1. Models         (Pydantic models + enums — no dependencies)
2. Storage        (needs models)
3. Services       (needs models + storage)
4. Routers        (needs models + services)
5. App wiring     (needs routers)
6. Demo files     (needs a running server to verify)
7. Documentation  (needs everything above to be accurate)
```

If you are adding a new feature (e.g. auto-classification):
- Add the model changes first
- Add the service function
- Add the route
- Verify it works end-to-end
- Then document it

---

## Chain of Thought: When to Show It

Show your reasoning explicitly for:

- **Debugging** — what you suspect, why, and what you ruled out
- **Design decisions** — why this approach over alternatives
- **Normalization logic** — which step handles which edge case and why
- **Error classification** — why this returns 400 vs 422 vs 415

Short chain of thought example:
```
Problem: Tags field causes import failure when CSV cell is empty.

Step 1: Trace the failure.
  Empty CSV cell → _normalize_empty_strings converts "" → None
  _normalize_tags then receives None → tries to split None → crashes

Step 2: Identify the fix.
  _normalize_tags should treat None as "no tags provided" → return []
  The existing check `if isinstance(tags_value, str)` misses None

Step 3: Apply the fix.
  Add: `if tags_value is None or tags_value == "": row["tags"] = []`

Step 4: Verify.
  Re-run CSV import → all 15 rows pass.
```

---

## Asking Clarifying Questions

Ask when:
- The requirement has two or more valid interpretations
- The scope of the change isn't clear (which phase? which endpoint?)
- A change would break an existing behaviour
- You need to choose between trade-offs (e.g. strict vs. lenient validation)

Do not ask when:
- The answer is clearly derivable from the existing code or docs
- It is a minor implementation detail with an obvious default
- The TASKS.md or PLAN.md already answers it

Format of a good question:
```
Context: [what you understand so far]
Options: [the two or more valid interpretations]
Default: [what you would do if forced to choose]
Question: [what you need to know to decide]
```

---

## Rules for Modifying Existing Code

1. **Read the file before editing it.** Never edit based on memory or assumption.
2. **Understand the full function before changing part of it.** Side effects are often in the parts you didn't read.
3. **Do not change the normalization order** without tracing the full pipeline.
4. **Do not change HTTP status codes** without checking the status code table in CLAUDE.md.
5. **Do not add business logic to routers.** Move it to a service function.
6. **Do not bypass Pydantic validation.** If a field needs special handling, add a `@field_validator`.

---

## Rules for Adding New Endpoints

1. Define or extend the Pydantic model in `src/models/ticket.py` first.
2. Add the business logic as a new function in the appropriate service.
3. Add the route handler in `src/routers/tickets.py` — keep it thin.
4. Register the router in `src/main.py` if it is a new router (not needed for the tickets router).
5. Add a cURL example to [HOWTORUN.md](HOWTORUN.md).
6. Add a full endpoint section to [docs/API_REFERENCE.md](docs/API_REFERENCE.md).

---

## Rules for Adding New Import Formats

1. Add a new `import_<format>()` function in `src/services/import_service.py`.
2. All format-specific parsing happens *before* calling `_process_rows()`.
3. All rows must pass through `_normalize_row()` before `_validate_and_create_row()`.
4. Add a demo file in `demo/` and verify 100% import success.
5. Register the new extension in the router's `if/elif` block in `src/routers/tickets.py`.
6. Add the format to the `415` error message so it lists all supported types.
7. Document the file format requirements in [docs/API_REFERENCE.md](docs/API_REFERENCE.md).

---

## Documentation Standards

All documentation must be:
- **Accurate** — reflects the actual code behaviour, not the intended behaviour
- **Linked** — every doc references related docs (see "Related Documents" sections)
- **Verified** — cURL examples must be tested before being committed to docs
- **Audience-aware** — README for developers, API_REFERENCE for consumers, ARCHITECTURE for tech leads

Cross-linking map:

```
README.md
  └── HOWTORUN.md
  └── docs/API_REFERENCE.md
  └── docs/ARCHITECTURE.md
  └── docs/PLAN.md

docs/PLAN.md
  └── docs/API_REFERENCE.md
  └── docs/ARCHITECTURE.md
  └── HOWTORUN.md

Every doc in docs/
  └── ../README.md  (link back to root)
```

---

## Anti-Patterns to Avoid

| Anti-Pattern | Why It's Harmful | What to Do Instead |
|--------------|------------------|--------------------|
| Implement without reading the existing code | Creates duplication, breaks conventions | Always explore first |
| Report done without verifying | Bugs ship to the next phase | Run a real request before saying done |
| Add logic to the router | Makes testing and reuse impossible | Put it in a service |
| Use Pydantic v1 API | Silent errors, deprecation warnings | Use `model_dump()`, `model_copy()`, etc. |
| Assume ambiguous requirements | Wrong implementation, wasted work | Ask a clarifying question |
| Skip the normalization pipeline | Import failures on real-world files | Always run through `_normalize_row()` |
| Giant commits | Hard to review, hard to revert | One logical change per commit |
| Write docs from memory | Inaccurate examples | Generate examples from a live server |

---

## Quick Reference

```bash
# Start server
uvicorn src.main:app --reload

# Verify all three import formats
curl -s -X POST http://localhost:8000/tickets/import -F "file=@demo/sample_tickets.csv" \
  | python3 -c "import json,sys; d=json.load(sys.stdin); print('CSV:', d['successful'], '/', d['total'])"

curl -s -X POST http://localhost:8000/tickets/import -F "file=@demo/sample_tickets.json" \
  | python3 -c "import json,sys; d=json.load(sys.stdin); print('JSON:', d['successful'], '/', d['total'])"

curl -s -X POST http://localhost:8000/tickets/import -F "file=@demo/sample_tickets.xml" \
  | python3 -c "import json,sys; d=json.load(sys.stdin); print('XML:', d['successful'], '/', d['total'])"
```

**Expected output after any code change:**
```
CSV: 15 / 15
JSON: 7 / 7
XML: 7 / 7
```

---

*For code-level rules and project conventions, see [CLAUDE.md](CLAUDE.md).*
*For architecture decisions and phase status, see [docs/PLAN.md](docs/PLAN.md).*
*For the original assignment requirements, see [TASKS.md](TASKS.md).*
