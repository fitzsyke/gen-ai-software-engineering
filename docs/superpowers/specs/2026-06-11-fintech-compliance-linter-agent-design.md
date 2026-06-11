# Design: Fintech Compliance Linter Agent

**Date:** 2026-06-11  
**Status:** Approved  
**Location:** `.claude/agents/fintech-compliance-linter.md` (project-level)

---

## Overview

A Claude Code subagent that reviews code in the P2P payment platform against the project's PCI-DSS compliance rules defined in `homework-3/.claude/fintech-rules.md` and `homework-3/agents.md`. Invoked by the developer when writing or reviewing payment-adjacent code.

---

## Agent Identity

| Field | Value |
|-------|-------|
| File | `.claude/agents/fintech-compliance-linter.md` |
| Name | `fintech-compliance-linter` |
| Model | `claude-sonnet-4-6` |
| Tools | `Read`, `Bash`, `Glob` |

**Description (used by Claude Code to decide when to invoke):**  
Use when writing or reviewing any code in the P2P payment platform that touches money arithmetic, ledger operations, payment routes, webhook handlers, secrets, or logging. Checks code against the project's PCI-DSS compliance rules.

---

## Rule Groups

The agent checks nine rule groups in order. Each finding is reported as PASS / FAIL / N/A.

| ID | Group | What is checked |
|----|-------|----------------|
| MONEY | Money arithmetic | No `parseFloat`, `Number()`, `Math.round/floor/ceil` on monetary values; all amounts use `BigInt` |
| DB | Database column types | No `NUMERIC`, `DECIMAL`, `FLOAT`, `REAL` in SQL migrations |
| MW | Middleware chain | Payment routes follow `authMiddleware → userGuard → idempotencyMiddleware → rateLimit → handler` in that exact order |
| WEBHOOK | Webhook handlers | Use `express.raw()` body parser; signature verification is the first operation before any DB call or body parsing |
| SECRET | Secret handling | No `process.env` for secrets; uses `SecretsManager`; no credentials in source files |
| LOG | Logging discipline | No `console.log/error/debug`; uses `pino` with structured schema; `bigint` amounts are `.toString()`-ed before logging |
| SQL | SQL safety | No string interpolation in queries; parameterized queries only |
| LEDGER | Ledger integrity | No `UPDATE`/`DELETE` on `ledger_entries`; wallet mutations inside `SERIALIZABLE` transactions with `FOR UPDATE` locks in UUID-ascending order |
| PAN | Raw card data | No PAN/CVV/card number accepted on server side; only Stripe `pm_*` tokens handled |

---

## Input

The user passes a file path, glob pattern, or describes what they just wrote. The agent reads the relevant files itself using `Read`, `Bash`, and `Glob`.

---

## Output Format

```
## Compliance Report: <file path(s)>

### PASS
- [RULE-ID] Description of what passed

### FAIL
- [RULE-ID] Description of violation — file:line — what was found vs. what is required

### N/A
- [RULE-ID] Why this rule does not apply to the reviewed file
```

- If no violations: states "All applicable rules pass." explicitly — never silently skips.
- Each FAIL references the specific rule from `agents.md` or `fintech-rules.md` so the developer can look it up.
- Never invents rules not present in the source documents.

---

## Behavior Constraints

- The agent reads `homework-3/.claude/fintech-rules.md` and `homework-3/agents.md` at the start of each invocation to ensure it uses the current rule set, not a cached version.
- Scope is limited to the files passed by the user — it does not crawl the entire repo unprompted.
- If a file does not exist or cannot be read, the agent reports this explicitly rather than silently skipping.
