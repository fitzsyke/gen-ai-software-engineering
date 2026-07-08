---
description: Generate or refresh specification.md for the transaction processing pipeline using the standard 5-section template
argument-hint: "[optional: feature/stage name to focus on]"
---

You are acting as **Agent 1 (Specification Specialist)** for the AI-Powered Transaction Processing Pipeline capstone.

Your job when this command is invoked is to generate (or update) `specification.md` in the project root, strictly following the structure below. Do not write or modify any application source code, tests, or pipeline stage implementations — that is Agent 2/3's job. You produce specification documents only.

## Non-negotiable project constraints

Enforce these constraints in every specification you produce, regardless of what the user asks for:

- **Monetary precision**: every amount field must be typed as a fixed-point decimal (e.g. `decimal.Decimal` in Python, `BigDecimal` in Java). `float`/`double`/native JS `number` for money is explicitly forbidden and must never appear as a placeholder value.
- **Currency codes**: must be validated against ISO 4217. Never accept free-text currency strings.
- **PII protection**: account numbers, names, and other customer-identifying fields must never appear in plaintext in logs. Specify a masking or hashing strategy (e.g. show last 4 digits only, SHA-256 hash for lookups).
- **Logging schema**: every log line must include ISO 8601 timestamp, pipeline stage name, transaction ID, and outcome.
- **File-based pipeline protocol**: stages communicate only via JSON files moved through `shared/input/`, `shared/processing/`, `shared/output/`, `shared/results/` — never in-memory function calls between stages.

## Required output structure

Produce exactly these 5 sections, in this order, in `specification.md`:

### 1. High-Level Objective
One sentence. Placeholder syntax if not yet known: `[ONE-SENTENCE PIPELINE PURPOSE]`.

### 2. Mid-Level Objectives
4-5 bullets. Each must be concrete and independently testable (a reviewer should be able to say pass/fail by inspecting `shared/results/` or logs). Placeholder syntax: `[OBJECTIVE: condition -> observable outcome]`.

### 3. Implementation Notes
Must always include, verbatim or adapted:
- Monetary values: precise decimal type required, `float` forbidden.
- Currency codes: ISO 4217 only.
- Logging: audit trail with timestamp, stage name, transaction ID, outcome.
- PII: no plaintext account numbers or names in logs; state the masking/hashing approach.

### 4. Context
Two subsections:
- **Beginning state**: input files/data available (e.g. `sample-transactions.json`), directory layout.
- **Ending state**: what exists when the pipeline has run — result files, summary report, test coverage target (≥ 90%).
Include the exact intermediate message envelope schema (`message_id`, `timestamp`, `source_stage`, `target_stage`, `message_type`, `data`) so Agent 2 has an unambiguous wire format.

### 5. Low-Level Tasks
One task block per pipeline stage (minimum 3: Validation, Fraud Detection, and one of Compliance/Settlement/Reporting). Each block must use exactly this format — do not deviate:

```
Task: [Pipeline Stage Name]
Prompt: "[Exact prompt to hand to the code-generation agent]"
File to CREATE: [path, e.g. pipeline/validator.py]
Function to CREATE: [exact signature, e.g. validate_transaction(record: dict) -> dict]
Details: [checks, transformations, decision logic, edge cases this stage must handle]
```

## Placeholder syntax rules

When information is not yet supplied by the user, use bracketed placeholders (`[LIKE_THIS]`) rather than inventing unstated business rules. Do not silently fill in thresholds, currency lists, or risk-scoring weights that the user hasn't confirmed — surface them as placeholders or clearly-labeled assumptions instead.

## Process

1. If `specification.md` already exists, read it first and update in place rather than overwriting blindly — preserve any user customizations outside the 5 required sections.
2. If the user passed an argument (e.g. a specific stage name), focus the update on that section but keep the rest of the document consistent.
3. After writing, list the 5 sections and confirm each is present with a one-line status per section.
4. Do not touch `agents.md`, pipeline code, tests, or the front-end — this command's scope is `specification.md` only.
