# P2P Payment Platform — Specification Package

**Author:** Artem Saienko  
**Homework:** HW-3 — Specification-Driven Design  
**Date:** 2026-06-05

---

## Summary

This package contains the complete specification and AI-agent configuration for a PCI-DSS Level 1-compliant peer-to-peer payment platform built on Node.js and React. No application source code is included — the deliverable is the specification itself: a multi-level blueprint an engineering team and AI coding agent could execute without ambiguity.

**Files in this package:**

| File | Purpose |
|------|---------|
| [`specification.md`](specification.md) | Full layered spec: objectives → data models → FSM → integration contracts → failure matrix → SLOs → low-level tasks |
| [`agents.md`](agents.md) | Operational rules for AI coding companions working in this codebase |
| [`.claude/fintech-rules.md`](.claude/fintech-rules.md) | Claude Code workspace configuration: file-glob-specific rules, migration auto-checks, forbidden patterns |
| [`README.md`](README.md) | This document: ADRs, math rationale, idempotency rationale, traceability matrix |

---

## Architectural Decision Records (ADRs)

### ADR-001: Double-Entry Ledger with Immutable Append-Only Rows

**Status:** Accepted

**Context:** A P2P payment system must provide an authoritative, auditable record of every balance change. Simple `balance += amount` row updates create a system where the current state is known but the history is not recoverable without separate audit tables — a compliance and forensics liability.

**Decision:** All financial state is expressed as an append-only ledger of `(DEBIT, wallet_id, amount)` and `(CREDIT, wallet_id, amount)` rows. The `wallet.balance_cents` column is a materialized cache of the ledger sum, maintained synchronously within the same transaction that writes ledger entries. Database rules prevent any `UPDATE` or `DELETE` on `ledger_entries`.

**Consequences:**
- *Easier:* Full audit trail is inherent in the data model. Any compliance query is a `SELECT` on the ledger. Chain hash integrity is checkable at any time. Forensic reconstruction after an incident is trivial.
- *Harder:* Correcting errors requires compensating entries (a new debit/credit pair), not in-place correction. The table grows monotonically, requiring archival strategy at scale. Balance reads join two sources (wallet cache + ledger), requiring reconciliation to stay consistent.
- *Trade-off accepted:* The compliance benefit of full auditability outweighs the operational complexity of compensating entries, especially in a regulated FinTech environment where auditability is a hard legal requirement.

---

### ADR-002: SERIALIZABLE Isolation Level for All Ledger Transactions

**Status:** Accepted

**Context:** PostgreSQL's default isolation level `READ COMMITTED` allows phantom reads and non-repeatable reads. In a concurrent payment system where two transfers from the same sender may execute simultaneously, `READ COMMITTED` can allow both transfers to read the same pre-debit balance and both to succeed — creating an overdraft.

**Decision:** All transactions that read and write `wallet.balance_cents` or `ledger_entries` use `ISOLATION LEVEL SERIALIZABLE`. Additionally, the two wallet rows are locked with `SELECT FOR UPDATE` in consistent ascending UUID order at the start of every transfer transaction.

**Consequences:**
- *Easier:* The database enforces serializability, eliminating an entire class of concurrent-write bugs without application-layer logic.
- *Harder:* `SERIALIZABLE` isolation has higher overhead than `READ COMMITTED` (roughly 10–15% throughput reduction under high contention). PostgreSQL may abort transactions with serialization failure errors (`ERROR 40001`), requiring retry logic.
- *Trade-off accepted:* The throughput cost is justified by the elimination of double-spend bugs. Retry logic (max 3 retries, exponential backoff) is a well-understood pattern that handles serialization failures correctly. The wallet lock ordering (ascending UUID) prevents deadlocks, keeping the retry rate low.

---

### ADR-003: Client-Generated UUID v4 Idempotency Keys

**Status:** Accepted

**Context:** P2P transfers over mobile networks are subject to network interruptions mid-request. Without idempotency, a client that times out and retries does not know whether the first request succeeded — leading to double charges. Server-generated idempotency (e.g., deduplication by request content hash) requires the server to store and compare full request bodies, which is expensive.

**Decision:** Clients generate a UUID v4 idempotency key before sending a transfer request. The key travels in the `x-idempotency-key` HTTP header / gRPC metadata. The server stores keys in `idempotency_keys` table with a 24-hour TTL and a Redis distributed lock to prevent concurrent duplicate execution.

**Consequences:**
- *Easier:* The client has full control over retry semantics. The server's deduplication logic is O(1) key lookup, not content comparison. The pattern composes naturally with mobile retry libraries.
- *Harder:* The client must generate and persist the key across retries. If the client loses the key (e.g., app crash), the retry will be treated as a new request. The 24-hour TTL means very long retries may re-execute.
- *Trade-off accepted:* Client-generated keys are the industry standard (used by Stripe, Plaid, and most FinTech APIs). The app crash scenario is handled by the UI storing the key in `AsyncStorage` before submission. 24-hour TTL covers all realistic retry windows.

---

### ADR-004: Stripe for Card Processing, Plaid for ACH — No In-House Card Processing

**Status:** Accepted

**Context:** Achieving PCI-DSS Level 1 compliance independently requires building a Cardholder Data Environment (CDE) with dedicated infrastructure, quarterly penetration tests, annual QSA audits, and WAF requirements — a multi-million dollar investment appropriate for a large payment processor, not an early-stage P2P application.

**Decision:** Card payment processing is fully delegated to Stripe. Raw card data is collected exclusively via Stripe.js / Stripe Elements in the browser; it never reaches our servers. Our servers store only Stripe `PaymentMethod` tokens (`pm_xxx`). ACH bank linking is delegated to Plaid. We store only Plaid `access_token` (encrypted) and masked bank account metadata.

**Consequences:**
- *Easier:* Our PCI-DSS scope is dramatically reduced to SAQ A (Stripe) — we are not in scope for raw PAN storage, transmission, or processing. Compliance is achievable with a small team. Stripe's fraud detection, 3DS handling, and dispute management are inherited for free.
- *Harder:* We are dependent on Stripe and Plaid's availability and pricing. Switching card processors later requires migrating tokenized card data, which requires Stripe's cooperation (network tokenization). We cannot build card-specific features (e.g., custom authorization rules) without going through Stripe's API surface.
- *Trade-off accepted:* The compliance scope reduction alone justifies this decision. The cost and risk of independent PCI-DSS Level 1 certification far exceeds the vendor dependency risk for an early-stage product.

---

### ADR-005: Modular Monolith Architecture (Not Microservices)

**Status:** Accepted

**Context:** Microservices offer independent scalability and team autonomy but introduce distributed systems complexity (distributed transactions, inter-service latency, complex deployment). For a P2P payment system where the ledger invariant requires atomic writes across multiple tables, distributed transactions (sagas, 2PC) add significant correctness risk and operational burden.

**Decision:** The backend is a single Node.js application with clearly separated modules (`services/`, `routes/`, `jobs/`, `db/`). Internal service-to-service communication that would cross microservice boundaries instead uses function calls within the monolith. The only exception is the internal gRPC interface documented in `specification.md Layer C.1`, which is designed to be extractable later.

**Consequences:**
- *Easier:* All ledger operations happen in a single database transaction — no distributed transaction coordination needed. Deployment, debugging, and local development are simpler. A small team can iterate quickly.
- *Harder:* The entire application must scale together. Database contention is a single point of failure. As the team grows, module boundaries must be actively maintained to prevent the codebase from becoming a "big ball of mud."
- *Trade-off accepted:* At MVP scale (< 1M users), a well-structured modular monolith outperforms a premature microservices architecture in reliability, development speed, and correctness. The gRPC interface definitions provide a clear extraction point when microservices become genuinely necessary.

---

## Math Engine Rationale: Why Integer Cents, Not Floats

### The Float Problem in Financial Software

IEEE 754 double-precision floating point cannot represent most decimal fractions exactly. The canonical example:

```javascript
> 0.1 + 0.2
0.30000000000000004
```

In financial systems, this error compounds across operations. A loan amortization schedule computed with floats will drift by cents over time, accumulating to meaningful discrepancies over thousands of transactions. In a regulated environment, a $0.01 discrepancy in a ledger is not a rounding error — it is a compliance finding.

More concretely, consider a system that accumulates a 1.5% fee on 1,000 transactions of $10.00:

- **Float:** `1000 × 10.00 × 0.015 = 150.00000000000003` — introduces rounding artifacts.
- **Integer (cents):** `1000 × 1000 × 15 / 1000 = 15000 cents = $150.00` — exact.

### Our Approach

- Every monetary value is stored as a `BIGINT` count of the smallest currency unit (cents for USD, pence for GBP, etc.).
- All arithmetic is performed in integer space. No intermediate float is ever produced.
- Display formatting (`Intl.NumberFormat`) is the only place where division by 100 occurs, and it is purely cosmetic — the result is never stored or used in further calculation.
- Where rounding is unavoidable (e.g., fee calculation: `(amount_cents × 15) / 1000` for a 1.5% fee), we apply **Bankers' Rounding (round-half-to-even)** via `bignumber.js` with `ROUND_HALF_EVEN`. This mode is statistically unbiased across large transaction volumes, unlike `ROUND_HALF_UP` which systematically rounds away from zero and can produce systematic overcharging.

### Why BigInt, Not a Decimal Library for All Arithmetic

`bignumber.js` and `decimal.js` are correct but carry overhead for simple add/subtract operations that constitute 99% of transfer arithmetic. PostgreSQL `BIGINT` arithmetic is native, fast, and exact. We use `bignumber.js` only at rounding boundaries. For everything else, native `BigInt` is used in Node.js and `BIGINT` in PostgreSQL.

---

## Idempotency Rationale: Preventing Double-Charges Over Patchy Networks

### The Problem

A mobile client submits a transfer request over LTE. The request reaches the server, the transfer is processed and committed, but the server's response is lost (TCP timeout, client app backgrounded, cell tower handoff). The client, receiving no confirmation, retries the request. Without idempotency, this creates a second transfer.

This is not a theoretical failure mode. It is the most common source of double-charges in production payment systems. The industry term is "at-least-once delivery" — networks guarantee delivery of requests at least once, but may deliver them more than once.

### Our Mitigation

1. **Client-generated idempotency key:** The client generates a UUID v4 before sending the request and stores it in local storage. It sends this key with every submission of the same logical transfer.

2. **Server-side deduplication:** The server checks the `idempotency_keys` table (Redis cache → DB) before executing. If the key is found, the original response is returned immediately — no second execution.

3. **Distributed lock:** A Redis lock (TTL: 30 seconds) ensures that if two requests with the same key arrive simultaneously (race condition during retry), only one executes. The second waits for the lock and then receives the cached response from the first.

4. **24-hour TTL:** The key is retained for 24 hours, covering any realistic retry window. After 24 hours, the key is eligible for cleanup. If a client retries after 24 hours, it should generate a new key — the original transfer's status is checkable via `GetTransfer`.

5. **Key scoping:** Keys are scoped to `(user_id, idempotency_key, endpoint)`. A key valid for `InitiateTransfer` cannot be replayed against `FundWallet`, preventing replay-attack misuse.

This mechanism guarantees **exactly-once** financial semantics over an **at-least-once** delivery network — the fundamental challenge of distributed payment systems.

---

## Regulatory Traceability Matrix

The following table maps specification sections to the real-world regulatory requirements they satisfy. This demonstrates that the specification is not over-engineered — each control exists to satisfy a specific, enforceable compliance obligation.

| Spec Section | Regulatory Requirement | Standard | How it's Satisfied |
|---|---|---|---|
| [Layer A.3: Integer Arithmetic & Bankers' Rounding](specification.md#a3-financial-mathematics-invariants) | Accuracy of financial records | GAAP / IFRS | Integer cents + Bankers' Rounding eliminate float drift; ledger invariant checked nightly |
| [Layer B.1.3: Immutable Ledger (`no_update_ledger` rule)](specification.md#b13-transaction-ledger-insert-only) | Integrity and completeness of audit records | PCI-DSS Req. 10.3 | PostgreSQL rules prevent UPDATE/DELETE; chain hashes detect tampering |
| [Layer B.3: AES-256 at rest, TLS 1.3 in transit](specification.md#b3-security-boundary) | Protect stored cardholder data; encrypt transmission | PCI-DSS Req. 3, Req. 4 | AES-256-GCM for PII fields; TLS 1.3 enforced at load balancer; no raw PAN stored |
| [Layer A.2: KYC via Persona; OFAC check](specification.md#a2-kycaml-trigger-policies) | Customer identification; OFAC screening | BSA/AML (31 CFR 1020.220); OFAC SDN list | Persona identity verification required before any financial op; OFAC match → hard block |
| [Layer A.2: CTR / SAR thresholds ($3,000, $10,000)](specification.md#a2-kycaml-trigger-policies) | Currency Transaction Reporting; Suspicious Activity Reporting | FinCEN (31 CFR 1010.311, 1020.320) | Transfers ≥ $3,000 auto-flagged for SAR review; 30-day cumulative > $10,000 triggers enhanced monitoring |
| [Layer B.3: Zero PAN/CVV storage; Stripe tokenization](specification.md#b3-security-boundary) | Do not store sensitive authentication data after authorization | PCI-DSS Req. 3.2 | Stripe.js collects card data client-side; server receives only `pm_xxx` token |
| [Layer C.1: gRPC mandatory idempotency key](specification.md#c1-grpc-service-definitions) | Non-repudiation; transaction uniqueness | PCI-DSS Req. 10.2 | Every transaction has a unique idempotency key; replays are detectable and audited |
| [Layer B.3: Audit log for every state transition](specification.md#b3-security-boundary) | Log all access to cardholder data; all authentication events | PCI-DSS Req. 10.2, 10.3 | Structured `pino` logs + `audit_log` table record all state transitions, API requests, and auth events |
| [Layer B.3: Secrets Manager; no keys in code](specification.md#b3-security-boundary) | Protect cryptographic keys; key management procedures | PCI-DSS Req. 3.5, Req. 3.6 | AWS Secrets Manager; 90-day Stripe key rotation; 30-day JWT key rotation |
| [Layer B.3: MFA enforcement](specification.md#b3-security-boundary) | Multi-factor authentication for access to CDE | PCI-DSS Req. 8.4 | TOTP MFA mandatory before first financial transaction; enforced server-side |
| [Task 10: Nightly reconciliation job](specification.md#task-10--nightly-reconciliation-job) | Balance verification; detection of unauthorized changes | PCI-DSS Req. 11.5; SOC 2 CC6.8 | Nightly job verifies ledger invariant and chain hash integrity; any discrepancy triggers P0 alert |
| [Layer A.1.1: User status FSM (FROZEN, CLOSED)](specification.md#a11-onboarding-journey) | Ability to restrict accounts under investigation | FinCEN SAR obligations; OFAC 31 CFR 501 | FROZEN status hard-blocks all financial operations; enforced in service layer, not UI |
| [Edge Case: Stripe amount mismatch on webhook](specification.md#edge-cases--failure-matrix) | Integrity of payment processing; detect fraudulent webhooks | PCI-DSS Req. 6.4 (injection protection) | Amount in webhook validated against DB record; mismatch → P1 alert, no state change |
| [Layer C.2.1: Plaid webhook idempotency](specification.md#c21-plaid-ach-bank-linking--transfer) | Exactly-once settlement; no double-credit | Reg E (12 CFR 1005) — error resolution | `processed_webhooks` table with `UNIQUE(event_id)` prevents double-crediting from duplicate delivery |
| [Data Retention Policy](specification.md#data-retention-policy) | Minimum 5-year retention for BSA records; 7-year for financial records | FinCEN (31 CFR 1010.430); IRS (IRC § 6501); civil limitation periods | Hot storage 2 years; cold-archived to S3 WORM years 3–7; `legal_holds` table prevents premature deletion |
| [Layer A.3.2: Tiered Fee Calculation — integer BigInt arithmetic](specification.md#a32-tiered-fee-structure) | Accuracy of disclosed fee amounts; prevention of rounding errors that could constitute overcharging | CFPB TILA (Reg Z) — accurate fee disclosure; UDAAP | Integer basis-point arithmetic + Bankers' Rounding ensures disclosed and charged fees are identical to the cent |
| [Layer A.1.5: Withdrawal journey — Stripe Instant Payouts](specification.md#a15-withdrawal-journey-stripe-instant-payouts--push-to-debit) | Consumer right to access funds; debit card funding validation | Reg E (12 CFR 1005.6) — consumer liability; network rules (Visa Direct, Mastercard Send) | Debit card type checked (`card.funding == 'debit'`); credit/prepaid rejected; compensating entries on payout failure guarantee balance integrity |
| [Task 13: Handle lookup returns `RECIPIENT_NOT_FOUND` for non-VERIFIED users](specification.md#task-13--handle-registration--lookup-service) | Prevention of account enumeration; privacy of KYC status | CCPA (Cal. Civ. Code § 1798.100) — right not to have personal information disclosed | Same error code for missing handle and non-VERIFIED handle prevents attackers from inferring account status |

---

## Industry Best Practices Incorporated

| Practice | Where in Spec | Why It Matters |
|---|---|---|
| Double-entry bookkeeping | `specification.md` Layer B.1.3 | The foundation of financial accounting since the 15th century; provides inherent error detection via ledger invariant |
| Idempotent APIs with client-generated keys | `specification.md` Layer C.1; `agents.md` §3.2 | Industry standard from Stripe, Plaid, Adyen; the only reliable defense against double-charges on unreliable networks |
| Finite state machine for transaction lifecycle | `specification.md` Layer B.2 | Explicit state machines prevent illegal state transitions (e.g., CLEARED → FAILED) that cause compliance issues |
| Webhook signature verification first | `agents.md` §3.5; `.claude/fintech-rules.md` | OWASP API Security Top 10 — prevents fraudulent webhook injection attacks |
| Wallet lock ordering for deadlock prevention | `specification.md` Layer A.1.4; `agents.md` §3.1 | Classic database deadlock prevention; consistent lock ordering is simpler and more reliable than retry-only approaches |
| AML velocity checks (rolling window) | `specification.md` Layer A.2 | FinCEN guidance on structuring detection; rolling windows catch rapid-fire transfer patterns that fixed daily windows miss |
| Integer cents with Bankers' Rounding | `specification.md` Layer A.3; `agents.md` §2.3 | IEEE 754 float arithmetic is inappropriate for money; Bankers' Rounding is unbiased over large transaction volumes |
| Cryptographic chain hashing of ledger | `specification.md` Layer B.1.3, Task 6 | Tamper-evident ledger without requiring a blockchain; detectable via reconciliation job |
| Redis distributed lock for idempotency | `agents.md` §3.2 | Prevents the concurrent-duplicate-request race condition that naive key-checking misses |
| Nightly reconciliation | `specification.md` Task 10; `agents.md` §5.1 | SOC 2 and PCI-DSS require periodic balance verification; automation catches discrepancies before they compound |
