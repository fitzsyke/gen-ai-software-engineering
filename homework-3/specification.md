# P2P Payment Application — Specification

> Ingest this file in full. Implement the Low-Level Tasks in order. Every task must satisfy the Mid-Level Objective it references. Do not proceed past a task until its acceptance criteria are met.

---

## High-Level Objective

Build a **PCI-DSS Level 1-compliant peer-to-peer payment platform** that allows verified users to fund a wallet via bank ACH or tokenized card, and instantly transfer value to other verified users through an immutable, double-entry ledger — with zero tolerance for float arithmetic, duplicate charges, or unaudited state transitions.

**Scope boundary:** This specification covers wallet funding, P2P transfer, ledger recording, KYC lifecycle, and the system's failure recovery contracts. Out of scope: merchant payments, crypto settlement, multi-currency conversion, and physical card issuance.

---

## Mid-Level Objectives

| ID | Objective | Observable Success Signal |
|----|-----------|--------------------------|
| MLO-1 | **Instant Atomic Internal Transfer** | A P2P transfer between two verified wallets completes or rolls back entirely within a single SERIALIZABLE database transaction; the ledger invariant `SUM(all debit entries) = SUM(all credit entries)` holds at all times |
| MLO-2 | **Distributed Idempotency Engine** | Re-submitting an identical transfer request (same client-generated idempotency key) within 24 hours returns the original response and produces zero duplicate ledger rows |
| MLO-3 | **KYC Lifecycle Integration** | A user without VERIFIED status cannot initiate a transfer or fund a wallet; the system enforces this as a hard gate at the service layer, not only the UI layer |
| MLO-4 | **Integer-Only Financial Arithmetic** | All monetary values in code, storage, and wire format are represented as 64-bit integers in the smallest currency unit (cents for USD); no `float`, `double`, or `NUMERIC(n,m)` type is used anywhere in the money path |
| MLO-5 | **Immutable Audit Ledger** | No ledger row is ever updated or deleted; all state is expressed via insert-only append; each row carries a cryptographic chain hash linking it to its predecessor |
| MLO-6 | **Zero Raw PAN/CVV Storage** | The system stores no raw card numbers, CVVs, or bank account credentials; all card data is represented by Stripe PaymentMethod tokens; bank account data is represented by Plaid access tokens scoped to a single institution |
| MLO-7 | **Operational Observability** | Every transaction state transition emits a structured log event to the audit trail; p99 latency, error rate, and ledger-balance-check pass/fail are exposed as Prometheus metrics |

---

## Layer A: Business & Compliance Logic

### A.1 User Journeys

#### A.1.1 Onboarding Journey

```
User registers (email + password + phone)
  → Account created with status = PROVISIONAL
  → Email verification link sent (expires 24 h)
  → User verifies email
  → Account transitions to status = EMAIL_VERIFIED
  → KYC flow triggered: user prompted for legal name, DOB, SSN-last-4, address
  → Identity document upload (government-issued ID)
  → Persona identity verification webhook received
      → PASS  → status = VERIFIED; wallet created with balance = 0
      → FAIL  → status = KYC_FAILED; user notified; manual review queued
      → PENDING (>72h) → status = KYC_REVIEW; ops team alerted
  → User selects a unique @handle (alphanumeric + underscore, 3–20 chars, case-preserved but compared case-insensitively)
      → System validates format (/^[a-zA-Z0-9_]{3,20}$/) and uniqueness (DB UNIQUE constraint on lowercase(handle))
      → Handle stored; exposed publicly for P2P lookup
  → MFA enrollment mandatory before first transaction (TOTP or SMS)
```

**Compliance gate:** A user in any state other than `VERIFIED` may not call `TransferFunds`, `FundWallet`, or `WithdrawFunds`. Enforcement occurs in the service layer `UserGuard` middleware, not relying on frontend gating.

#### A.1.2 Bank Authentication (Plaid Link)

```
User navigates to "Link Bank Account"
  → Frontend opens Plaid Link widget
  → User authenticates with their bank (OAuth or credential-based, per institution)
  → Plaid returns public_token
  → Backend exchanges public_token for access_token + item_id via Plaid /item/public_token/exchange
  → access_token stored encrypted (AES-256-GCM) in the payment_methods table (type = BANK_ACH)
  → Bank account metadata stored (institution name, masked account number last-4, account_id)
  → Raw bank credentials never touch our system
```

#### A.1.3 Wallet Funding Journey

```
User selects funding source (linked bank or saved card)
  → System checks: user.status == VERIFIED
  → System checks: funding amount > 0 AND amount ≤ daily_funding_limit (default $10,000)
  → System checks: idempotency key not already used within 24 h
  → For ACH:
      → Plaid Transfer API called with idempotency_key, amount_cents, access_token
      → Transfer record inserted: status = PENDING, external_ref = plaid_transfer_id
      → Webhook from Plaid on settlement: status → CLEARED → ledger credit rows inserted
  → For Card:
      → Stripe PaymentIntent created with idempotency_key, amount, payment_method_id
      → Transfer record inserted: status = PENDING, external_ref = stripe_payment_intent_id
      → Stripe webhook on payment_intent.succeeded → status → CLEARED → ledger credit rows inserted
  → Wallet balance is updated only after ledger rows are durably written (read-your-writes guaranteed)
```

#### A.1.4 P2P Transfer Execution Journey

```
Sender initiates transfer
  → Input validation (amount, recipient @handle, idempotency key, optional memo)
  → Handle lookup: `SELECT id FROM users WHERE lower(handle) = lower($1) AND status = 'VERIFIED'`
      → Not found → return `RECIPIENT_NOT_FOUND` error; no financial operation initiated
      → Found → resolve to recipient user_id and then to recipient wallet_id
  → System checks:
      (1) sender.status == VERIFIED
      (2) recipient.status == VERIFIED
      (3) sender wallet balance ≥ transfer_amount (in cents)
      (4) transfer_amount > 0
      (5) sender != recipient
      (6) idempotency key not already used within 24 h
      (7) transfer does not breach sender's daily_transfer_limit ($5,000 default)
      (8) AML velocity check: ≤ 10 transfers in any 60-minute rolling window per sender
  → BEGIN SERIALIZABLE TRANSACTION
      → Lock sender wallet row (SELECT FOR UPDATE)
      → Lock recipient wallet row (SELECT FOR UPDATE, always in consistent key-order to prevent deadlock)
      → Re-verify sender balance ≥ amount (phantom read protection)
      → Insert DEBIT ledger entry (sender, −amount, chain_hash)
      → Insert CREDIT ledger entry (recipient, +amount, chain_hash)
      → Insert transfer record (status=AUTHORIZED, idempotency_key, sender_id, recipient_id, amount_cents)
      → Update sender wallet.balance_cents −= amount
      → Update recipient wallet.balance_cents += amount
  → COMMIT
  → Async: push notification to recipient
  → Async: AML post-transaction screening (no blocking of settlement)
  → Return transfer record (status=CLEARED for internal transfers)
```

#### A.1.5 Withdrawal Journey (Stripe Instant Payouts — Push-to-Debit)

```
User navigates to "Withdraw Funds"
  → System checks: user.status == VERIFIED
  → System checks: user has a linked debit card with a Stripe PaymentMethod of type 'card' and card.funding == 'debit'
      → If no debit card linked: prompt user to add a debit card via Stripe Elements (SetupIntent flow)
  → User enters withdrawal amount
  → System checks: wallet.balance_cents >= withdrawal_amount_cents
  → System checks: withdrawal_amount_cents >= 100 (minimum $1.00; Stripe minimum)
  → System checks: withdrawal_amount_cents <= 1000000 (maximum $10,000.00 per Stripe Instant Payout limit)
  → Fee calculation (Stripe charges 1% for Instant Payouts, billed to us, passed to user):
      → payout_fee_cents = round_half_even(withdrawal_amount_cents × 100 / 10000)  -- 1% in basis points
      → net_payout_cents = withdrawal_amount_cents − payout_fee_cents
      → If net_payout_cents ≤ 0: return WITHDRAWAL_AMOUNT_TOO_SMALL error
  → User confirms: "You will receive ${net_payout_cents} (${payout_fee_cents} Instant Payout fee)"
  → BEGIN SERIALIZABLE TRANSACTION
      → Lock sender wallet (SELECT FOR UPDATE)
      → Re-verify balance ≥ withdrawal_amount_cents
      → Insert DEBIT ledger entry: amount = withdrawal_amount_cents (full amount leaves wallet)
      → Insert FEE ledger entry: amount = payout_fee_cents (separate entry, transfer_type = PAYOUT_FEE)
      → Update wallet.balance_cents −= withdrawal_amount_cents
      → Create transfers row: status = PENDING, type = WITHDRAWAL
  → COMMIT
  → Call Stripe /v1/payouts with:
      amount = net_payout_cents
      currency = 'usd'
      method = 'instant'
      destination = stripe_debit_card_payment_method_id
      metadata.transfer_id = transfer.id
  → Store stripe_payout_id as external_ref
  → Stripe webhook payout.paid → status = CLEARED
  → Stripe webhook payout.failed → status = FAILED → compensating CREDIT ledger entry inserted → balance restored
```

**Withdrawal Limits:** Maximum $10,000 per instant payout (Stripe platform limit). Minimum $1.00.
**Availability:** Instant Payouts settle within 30 minutes to the debit card. Available 24/7/365 including weekends and holidays.
**Debit card requirement:** Visa or Mastercard debit cards only. Prepaid cards and credit cards are rejected by Stripe at the API level.

---

### A.2 KYC/AML Trigger Policies

| Trigger | Policy | System Action |
|---------|--------|---------------|
| New user registration | Always | Initiate Persona identity verification before allowing any financial transaction |
| Persona webhook: FAILED | Hard block | Set `user.status = KYC_FAILED`; block all financial ops; send user notification |
| Persona webhook: NEEDS_REVIEW | Soft block | Set `user.status = KYC_REVIEW`; ops ticket created; user notified of delay |
| Transfer amount ≥ $3,000 in a single transaction | Regulatory (FinCEN) | Auto-flag for SAR review; still process transaction unless OFAC match |
| Cumulative transfers > $10,000 in any 30-day rolling window | CTR threshold proximity | Create compliance event; trigger enhanced monitoring flag on user |
| ≥ 10 P2P sends in 60 minutes | Velocity anomaly | Temporarily suspend transfers; require user re-authentication; alert fraud queue |
| Transfer to/from a user added to OFAC SDN list | Hard block | Deny transaction immediately; freeze both accounts; create SAR filing record |
| Account balance drops to zero then receives large deposit within 1 hour | Structuring signal | Flag for AML review; do not block automatically; escalate to compliance team |

---

### A.3 Financial Mathematics Invariants

#### A.3.1 Integer Arithmetic Mandate

- **All monetary values are stored and computed as `BIGINT` (64-bit signed integer) representing the number of cents (minor currency units).**
- `$10.00 USD` is stored as `1000` (cents). `$0.01` is `1`. Never `10.0`, `10.00`, or `"10.00"`.
- No `FLOAT`, `REAL`, `DOUBLE PRECISION`, or `NUMERIC(p,s)` column or variable may appear anywhere in the money computation path.
- Wire format: all API fields carrying monetary values use the type `integer` (JSON) and are documented in cents. Example: `{ "amount_cents": 1050 }` = $10.50.
- Language types: Node.js must use `BigInt` for any arithmetic involving amounts > `Number.MAX_SAFE_INTEGER` (unlikely in MVP but enforced for correctness). In practice, a plain `number` is safe for amounts under ~$90 trillion but the type annotation must be `bigint` to prevent accidental float coercion.

#### A.3.2 Tiered Fee Structure

**Policy:** The first $2,000 of P2P transfers per calendar month per sender is fee-free. Volume above $2,000 incurs a 2% fee on the overage, applied per transfer.

**Fee Tier Constant (configurable):**
```typescript
const FREE_TIER_CENTS = 200000n;   // $2,000.00
const FEE_BPS = 200n;              // 200 basis points = 2.00%
const BPS_DIVISOR = 10000n;        // basis points denominator
```

**Fee Calculation Algorithm (integer arithmetic):**
```typescript
function calculateTransferFee(amountCents: bigint, mtdVolumeCents: bigint): bigint {
  // How much of this transfer falls above the free tier?
  const tierRemaining = FREE_TIER_CENTS - mtdVolumeCents;
  if (tierRemaining <= 0n) {
    // Fully above free tier: fee applies to entire amount
    return roundHalfEven(amountCents * FEE_BPS, BPS_DIVISOR);
  }
  if (tierRemaining >= amountCents) {
    // Fully within free tier: no fee
    return 0n;
  }
  // Partially above free tier: fee applies only to the overage
  const chargeablePortion = amountCents - tierRemaining;
  return roundHalfEven(chargeablePortion * FEE_BPS, BPS_DIVISOR);
}

function roundHalfEven(numerator: bigint, denominator: bigint): bigint {
  // Bankers' Rounding implemented via bignumber.js — see A.3.3
  const bn = new BigNumber(numerator.toString())
    .dividedBy(denominator.toString())
    .integerValue(BigNumber.ROUND_HALF_EVEN);
  return BigInt(bn.toString());
}
```

**Month-to-date (MTD) volume tracking:**

```sql
-- Called at the start of each transfer to determine fee
SELECT COALESCE(SUM(amount_cents), 0)
FROM transfers
WHERE sender_wallet_id = $1
  AND status IN ('AUTHORIZED', 'CLEARED')
  AND transfer_type = 'INTERNAL'
  AND date_trunc('month', created_at AT TIME ZONE 'UTC') = date_trunc('month', now() AT TIME ZONE 'UTC');
```

This query runs inside the SERIALIZABLE transaction (after acquiring wallet locks) so MTD volume is consistent with in-flight transfers.

**Fee ledger entry:** When a fee is charged, two additional ledger entries are inserted within the same transaction:
- DEBIT on sender wallet: `amount = fee_cents`, `transfer_type = TRANSFER_FEE`
- CREDIT on a platform revenue wallet: `amount = fee_cents`, `transfer_type = TRANSFER_FEE`

The net debit to the sender wallet is `transfer_amount_cents + fee_cents`. The recipient receives exactly `transfer_amount_cents` (fees do not reduce the received amount).

#### A.3.3 Bankers' Rounding Definition (Round-Half-to-Even)

- Rounding is only permitted in two places: (a) fee calculation, (b) currency conversion (future scope).
- When rounding is required, the system must apply **round-half-to-even** (IEEE 754 `roundTiesToEven`):
  - `0.5 cents` rounds to `0` (even)
  - `1.5 cents` rounds to `2` (even)
- Implementation: use the `bignumber.js` library with `ROUND_HALF_EVEN` mode. Do not use JavaScript's `Math.round()` for money.

#### A.3.4 Ledger Balance Invariant

At all times, for every wallet `w`:

```
w.balance_cents = SUM(ledger_entries WHERE wallet_id = w.id AND type = CREDIT)
               − SUM(ledger_entries WHERE wallet_id = w.id AND type = DEBIT)
```

A nightly reconciliation job must verify this invariant for every wallet. Any discrepancy triggers a P0 alert and halts all transfers until resolved.

---

## Layer B: System Architecture & Data Layer

### B.1 Data Models

#### B.1.1 User

```sql
CREATE TABLE users (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email               TEXT UNIQUE NOT NULL,
  phone_e164          TEXT UNIQUE,
  handle              VARCHAR(20) UNIQUE NOT NULL,  -- @handle for P2P lookup, /^[a-zA-Z0-9_]{3,20}$/
  password_hash       TEXT NOT NULL,           -- bcrypt, cost factor ≥ 12
  status              user_status NOT NULL DEFAULT 'PROVISIONAL',
  kyc_provider_ref    TEXT,                    -- Persona inquiry ID
  mfa_secret_enc      BYTEA,                   -- AES-256-GCM encrypted TOTP seed
  daily_fund_limit_cents  BIGINT NOT NULL DEFAULT 1000000,  -- $10,000
  daily_xfer_limit_cents  BIGINT NOT NULL DEFAULT 500000,   -- $5,000
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  frozen_at           TIMESTAMPTZ,
  frozen_reason       TEXT
);

CREATE TYPE user_status AS ENUM (
  'PROVISIONAL',     -- registered, email not yet verified
  'EMAIL_VERIFIED',  -- email confirmed, KYC not started
  'KYC_PENDING',     -- KYC inquiry submitted, awaiting webhook
  'KYC_REVIEW',      -- Persona flagged for manual review
  'KYC_FAILED',      -- KYC definitively failed
  'VERIFIED',        -- full KYC passed, financial ops allowed
  'FROZEN',          -- compliance hold, all ops suspended
  'CLOSED'           -- account closed, read-only
);
```

#### B.1.2 Wallet

```sql
CREATE TABLE wallets (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id         UUID NOT NULL REFERENCES users(id),
  currency        CHAR(3) NOT NULL DEFAULT 'USD',
  balance_cents   BIGINT NOT NULL DEFAULT 0
                  CHECK (balance_cents >= 0),   -- no overdrafts in MVP
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (user_id, currency)
);
```

#### B.1.3 Transaction Ledger (Insert-Only)

```sql
CREATE TABLE ledger_entries (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  wallet_id       UUID NOT NULL REFERENCES wallets(id),
  transfer_id     UUID REFERENCES transfers(id),
  entry_type      ledger_entry_type NOT NULL,   -- DEBIT | CREDIT
  amount_cents    BIGINT NOT NULL CHECK (amount_cents > 0),
  balance_after_cents  BIGINT NOT NULL,         -- running balance snapshot
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  chain_hash      BYTEA NOT NULL,               -- SHA-256(prev_chain_hash || this_row_data)
  memo            TEXT
);

CREATE TYPE ledger_entry_type AS ENUM ('DEBIT', 'CREDIT');

-- Enforce immutability via rule
CREATE RULE no_update_ledger AS ON UPDATE TO ledger_entries DO INSTEAD NOTHING;
CREATE RULE no_delete_ledger AS ON DELETE TO ledger_entries DO INSTEAD NOTHING;
```

#### B.1.4 Transfer Record

```sql
CREATE TABLE transfers (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  idempotency_key     TEXT NOT NULL,
  sender_wallet_id    UUID NOT NULL REFERENCES wallets(id),
  recipient_wallet_id UUID NOT NULL REFERENCES wallets(id),
  amount_cents        BIGINT NOT NULL CHECK (amount_cents > 0),
  currency            CHAR(3) NOT NULL DEFAULT 'USD',
  status              transfer_status NOT NULL DEFAULT 'PENDING',
  transfer_type       transfer_type_enum NOT NULL,  -- INTERNAL | ACH_DEBIT | CARD_FUNDING | WITHDRAWAL
  external_ref        TEXT,                         -- Stripe PI id or Plaid transfer id
  initiated_by        UUID NOT NULL REFERENCES users(id),
  memo                TEXT,
  metadata            JSONB,                        -- non-financial metadata only
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  authorized_at       TIMESTAMPTZ,
  cleared_at          TIMESTAMPTZ,
  failed_at           TIMESTAMPTZ,
  failure_reason      TEXT,
  UNIQUE (idempotency_key)
);

CREATE TYPE transfer_status AS ENUM (
  'PENDING', 'AUTHORIZED', 'CLEARED', 'FAILED', 'REVERSED'
);
```

#### B.1.5 Idempotency Key Registry

```sql
CREATE TABLE idempotency_keys (
  key             TEXT PRIMARY KEY,
  user_id         UUID NOT NULL REFERENCES users(id),
  endpoint        TEXT NOT NULL,
  request_hash    BYTEA NOT NULL,    -- SHA-256 of canonical request body
  response_status INT NOT NULL,
  response_body   JSONB NOT NULL,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  expires_at      TIMESTAMPTZ NOT NULL DEFAULT (now() + INTERVAL '24 hours')
);

CREATE INDEX ON idempotency_keys (expires_at);  -- for TTL cleanup job
```

---

### B.2 Transaction Finite State Machine

```
                      ┌─────────────────────────────────────────────────┐
                      │              Transfer FSM                        │
                      └─────────────────────────────────────────────────┘

   Client Request
        │
        ▼
   ┌─────────┐   validation fails / balance   ┌────────┐
   │ PENDING │──────────────────────────────► │ FAILED │
   └─────────┘   insufficient / user frozen   └────────┘
        │                                          ▲
        │ all guards pass                          │
        ▼                                          │ external provider failure
   ┌────────────┐   DB commit succeeds (internal)  │ or network timeout
   │ AUTHORIZED │─────────────────────────────────►│
   └────────────┘                                  │
        │                                          │
        │ internal transfer / external webhook
        │ confirms settlement
        ▼
   ┌─────────┐
   │ CLEARED │
   └─────────┘
        │
        │ (future: dispute raised within 60 days)
        ▼
   ┌──────────┐
   │ REVERSED │ ◄── compliance forced reversal only; requires dual-approval
   └──────────┘
```

**FSM Rules:**
- State transitions are stored as append-only events, not in-place updates on the transfers row.
- `CLEARED → FAILED` is illegal. A cleared transfer may only become `REVERSED`.
- `REVERSED` requires a corresponding compensating ledger entry pair (DEBIT on recipient, CREDIT on sender) and a separate `transfers` row of type `REVERSAL`.

---

### B.3 Security Boundary

| Control | Implementation |
|---------|---------------|
| Encryption at rest | AES-256-GCM for all PII fields (SSN, bank tokens, TOTP seeds); PostgreSQL-level TDE via cloud provider (AWS RDS with KMS CMK) |
| Encryption in transit | TLS 1.3 mandatory; TLS 1.2 allowed only for Plaid webhook endpoints where client library mandates it; TLS 1.0/1.1 rejected at load balancer |
| PAN/CVV zero-storage | Stripe.js collects card data client-side; raw PAN never reaches our servers; Stripe PaymentMethod `pm_xxx` token is the only card identifier we store |
| Authentication | JWT (RS256, 15-minute access token) + refresh token (opaque, 30-day, stored as `SHA-256(token)` in DB) |
| MFA | TOTP (RFC 6238, 30-second window, ±1 window drift tolerance); mandatory before first financial transaction |
| Secrets management | AWS Secrets Manager for DB credentials, Stripe keys, Plaid secrets, Persona API keys; no secrets in environment variables or source code |
| Key rotation | Stripe webhook signing secrets rotated every 90 days; JWT signing keys rotated every 30 days with 5-minute overlap period |
| API security | Rate limiting: 100 requests/minute per authenticated user; 10 requests/minute per IP on auth endpoints |
| Input sanitization | All string inputs sanitized via `validator.js`; all SQL via parameterized queries (no string interpolation); no eval() or Function() in codebase |
| Audit log | Every API request and every state transition writes a structured JSON audit event to an append-only `audit_log` table and to a SIEM-compatible log stream |
| Network segmentation | Database accessible only from application subnets; no public database endpoint; admin access via AWS Systems Manager Session Manager only |

---

## Layer C: Interface & Integration Layer

### C.1 gRPC Service Definitions

All internal service-to-service communication uses gRPC with mTLS. The Transfer service exposes:

```protobuf
syntax = "proto3";
package payments.v1;

import "google/protobuf/timestamp.proto";

// ─── Transfer Service ────────────────────────────────────────────────────────

service TransferService {
  // Initiate a P2P transfer. Idempotency key must be set in gRPC metadata
  // under key "x-idempotency-key". Retry with same key is safe.
  rpc InitiateTransfer(InitiateTransferRequest) returns (TransferResponse);

  // Retrieve a transfer by ID or idempotency key.
  rpc GetTransfer(GetTransferRequest) returns (TransferResponse);

  // List transfers for the authenticated wallet (paginated, cursor-based).
  rpc ListTransfers(ListTransfersRequest) returns (ListTransfersResponse);
}

message InitiateTransferRequest {
  string sender_wallet_id    = 1;  // UUID
  string recipient_user_id   = 2;  // UUID (resolved to wallet server-side)
  int64  amount_cents        = 3;  // must be > 0
  string currency            = 4;  // ISO 4217, e.g. "USD"
  string memo                = 5;  // optional, max 140 chars
}

message GetTransferRequest {
  oneof identifier {
    string transfer_id      = 1;
    string idempotency_key  = 2;
  }
}

message ListTransfersRequest {
  string wallet_id   = 1;
  string cursor      = 2;   // opaque pagination cursor
  int32  page_size   = 3;   // max 100
  string direction   = 4;   // "SENT" | "RECEIVED" | "ALL"
}

message TransferResponse {
  string   transfer_id          = 1;
  string   idempotency_key      = 2;
  string   status               = 3;
  int64    amount_cents         = 4;
  string   currency             = 5;
  string   sender_wallet_id     = 6;
  string   recipient_wallet_id  = 7;
  google.protobuf.Timestamp created_at   = 8;
  google.protobuf.Timestamp cleared_at   = 9;
  string   failure_reason       = 10;
}

message ListTransfersResponse {
  repeated TransferResponse transfers = 1;
  string next_cursor                  = 2;
  bool   has_more                     = 3;
}
```

**Idempotency contract:** The `x-idempotency-key` gRPC metadata header is mandatory on `InitiateTransfer`. The server rejects any call missing this header with status `INVALID_ARGUMENT`. The key must be a UUID v4. The server caches responses for 24 hours keyed by `(user_id, idempotency_key, endpoint)`.

---

### C.2 Third-Party Integration Specifications

#### C.2.1 Plaid (ACH Bank Linking & Transfer)

| Action | Plaid API | Our System Action |
|--------|-----------|-------------------|
| Link bank account | `/link/token/create` → Plaid Link → `/item/public_token/exchange` | Store encrypted `access_token`; store masked account details |
| Initiate ACH debit (funding) | `/transfer/create` with `type=debit`, `idempotency_key`, `amount` | Create `transfers` row in PENDING; store `plaid_transfer_id` as `external_ref` |
| Receive settlement webhook | `transfer.events.update` with `event_type=settled` | Transition transfer to CLEARED; insert ledger entries; update wallet balance |
| Receive failure webhook | `transfer.events.update` with `event_type=failed` | Transition transfer to FAILED; no ledger entries; notify user |
| Webhook verification | Verify `Plaid-Verification` header using Plaid signing key | Reject any webhook with invalid signature; log and discard |

**Webhook idempotency:** Plaid may deliver the same webhook event multiple times. Our handler checks `event_id` against a `processed_webhooks` table before acting. Duplicate events are acknowledged (200 OK) and silently discarded.

#### C.2.2 Stripe (Card Processing)

| Action | Stripe API | Our System Action |
|--------|------------|-------------------|
| Save card | Stripe.js `confirmCardSetup` client-side → `SetupIntent` | Store `PaymentMethod.id` (`pm_xxx`); never store raw card data |
| Fund wallet via card | `/payment_intents/create` with `idempotency_key`, `payment_method`, `confirm=true` | Create `transfers` row in PENDING; store `payment_intent_id` as `external_ref` |
| Receive success webhook | `payment_intent.succeeded` | Transition to CLEARED; insert ledger entries; update balance |
| Receive failure webhook | `payment_intent.payment_failed` | Transition to FAILED; propagate decline code to user (never log raw decline reason to public logs) |
| Webhook verification | `stripe.webhooks.constructEvent(body, sig, secret)` | Reject any event with invalid signature; 400 response |

#### C.2.3 Stripe Payouts (Instant Withdrawal to Debit Card)

| Action | Stripe API | Our System Action |
|--------|------------|-------------------|
| Save debit card for payouts | Stripe Elements `SetupIntent` with `usage=on_session` | Store `PaymentMethod.id`; verify `card.funding == 'debit'`; reject if `funding == 'credit'` or `funding == 'prepaid'` |
| Initiate instant withdrawal | `POST /v1/payouts` with `method=instant`, `destination=pm_xxx`, `amount=net_payout_cents` | Create `transfers` row in PENDING (type=WITHDRAWAL); store `payout_id` as `external_ref` |
| Receive payout success webhook | `payout.paid` | Transition to CLEARED; no additional ledger entries (debit already written at initiation) |
| Receive payout failure webhook | `payout.failed` | Transition to FAILED; insert compensating CREDIT ledger entry; restore wallet balance; notify user with failure reason |
| Webhook verification | `stripe.webhooks.constructEvent` | Same pattern as card payment webhooks; raw body required |

**Payout failure handling:** If Stripe `payout.failed`, the system must atomically:
1. Insert a compensating CREDIT entry for `withdrawal_amount_cents` (full amount, including the fee that was debited)
2. Insert a compensating CREDIT entry for `payout_fee_cents` (fee refunded since payout didn't complete)
3. Update `transfers.status = FAILED`
4. Notify user with a mapped failure message (e.g., "Your debit card declined this payout. Please check your card details.")

#### C.2.4 Persona (KYC/Identity Verification)

| Action | Persona API | Our System Action |
|--------|-------------|-------------------|
| Start verification | POST `/inquiries` with `template_id`, `reference_id=user.id` | Store `inquiry_id` on user; set status = KYC_PENDING |
| Receive pass webhook | `inquiry.approved` | Set `user.status = VERIFIED`; create wallet; send welcome email |
| Receive fail webhook | `inquiry.declined` | Set `user.status = KYC_FAILED`; notify user; create compliance record |
| Receive review webhook | `inquiry.needs_review` | Set `user.status = KYC_REVIEW`; create ops ticket |
| Webhook verification | Verify `Persona-Signature` header | Reject unauthenticated webhooks; 401 response |

> **Note:** Persona was previously labeled C.2.3; renumbered to C.2.4 after Stripe Payouts insertion.

---

## Edge Cases & Failure Matrix

| Failure Mode | Detection Mechanism | System Behavior | Compliance Implication |
|---|---|---|---|
| Concurrent transfer requests (same sender, two simultaneous calls) | `SELECT FOR UPDATE` lock on sender wallet row inside SERIALIZABLE tx; second request blocks until first commits | Second request proceeds after first commits and re-reads balance; if balance now insufficient, returns `INSUFFICIENT_FUNDS` error | No duplicate debit; audit log shows both attempts; idempotency key prevents retries from doubling charge |
| Database deadlock mid-transaction | PostgreSQL deadlock detection (typically <1s); raises `ERROR 40P01` | Transaction is rolled back automatically; application retries up to 3 times with exponential backoff (100ms, 200ms, 400ms) starting with the lower wallet ID lock order; if 3 retries exhausted, returns 503 to client | Ledger stays consistent; no partial debit; transfer stays in PENDING until retry succeeds or fails terminally |
| Network isolation after partial debit (debit posted, credit not yet written) | Debit and credit rows are written in the same DB transaction; network isolation cannot split them | Impossible scenario: both writes are inside a single COMMIT; OS crash mid-commit results in full rollback on PostgreSQL WAL recovery | Ledger invariant maintained; no user-visible partial transfer |
| Transfer to a FROZEN recipient | Recipient status checked before acquiring wallet locks | Transfer denied with `RECIPIENT_FROZEN` error code; sender retains full balance; no ledger entries written | Audit log records the attempt; no funds move; compliant with OFAC hold requirements |
| Duplicate idempotency key from different users | Idempotency key table indexed on `(key)`; checked against `user_id` on lookup | If `key` exists for a different `user_id`, treat as new request (keys are user-scoped); if same `user_id`, return cached response | Prevents cross-user key collision attacks; audit trail shows the lookup |
| Plaid webhook delivered twice (at-least-once delivery) | `processed_webhooks` table with `UNIQUE(event_id)` | Second delivery: `INSERT ... ON CONFLICT DO NOTHING`; return 200; take no financial action | Exactly-once ledger semantics preserved |
| Stripe PaymentIntent amount mismatch (webhook amount ≠ transfer record amount) | On webhook receipt, compare `event.data.object.amount` to `transfers.amount_cents` | Reject the webhook; create a P1 alert; do not update transfer status; escalate for manual review | Prevents fraudulent webhook injection; PCI-DSS requirement for integrity validation |
| KYC status changes to FROZEN mid-session (user active) | Redis-cached user status TTL = 30 seconds; critical paths re-read from DB | Ongoing transfers in-flight are allowed to complete (already past auth gate); next API call within 30s may use stale VERIFIED status; next call after TTL expiry will be blocked | 30-second window is a deliberate trade-off: reduces DB load while bounding the exposure window; document in compliance runbook |
| Balance underflow (balance would go negative) | `CHECK (balance_cents >= 0)` DB constraint + application-layer pre-check | Application pre-check returns `INSUFFICIENT_FUNDS` before attempting DB write; DB constraint is final safety net | Double defense prevents overdraft; no silent negative balance |
| Ledger chain hash verification failure | Nightly reconciliation job re-computes chain hashes | Halt all transfers; P0 alert; incident response triggered | Indicates possible data tampering; requires forensic audit before operations resume |
| User submits transfer with amount = 0 or negative | Input validation layer (Zod schema on request body / gRPC message validation) | Returns `INVALID_AMOUNT` error before any DB interaction | Prevents zero-value or negative ledger entries |
| Daily transfer limit exceeded | Checked against `SUM(transfers.amount_cents WHERE sender = user AND date = today)` in application layer | Returns `DAILY_LIMIT_EXCEEDED` with remaining daily allowance in response | Implements AML velocity control; logged as compliance event |

---

## Performance & Verification SLOs

### Performance Targets (Assumed — FinTech UX-Justified)

| Metric | Target | Justification |
|--------|--------|---------------|
| P99 API latency — `InitiateTransfer` | ≤ 200ms (internal P2P) | Industry benchmark for payment UX; Venmo/Cash App at ~150ms; >500ms causes user re-submission |
| P99 API latency — `GetTransfer` | ≤ 50ms | Read-only query with index; no lock contention |
| P99 API latency — `FundWallet` (ACH) | ≤ 500ms (for initiating the Plaid call; actual settlement is async) | ACH initiation requires Plaid API call; 500ms acceptable for a deliberate funding action |
| Ledger read lag (balance after write) | 0ms (read-your-writes) | Wallet balance reads must query the primary DB replica within the same request context; no eventual consistency for balance reads |
| Idempotency key cache lookup | ≤ 5ms (Redis) | Cache-first lookup; DB fallback only on cache miss |
| Webhook processing throughput | ≥ 500 events/second | Peak during market hours; Plaid/Stripe may burst; queue must not back up |
| Nightly reconciliation job | Complete within 4-hour window (2:00 AM–6:00 AM UTC) | Must complete before US business hours; alerts fire at 5:00 AM if not complete |
| KYC webhook processing latency | ≤ 10 seconds end-to-end from Persona webhook to user status update | Affects user onboarding conversion; measure from webhook receipt to DB commit |

### Acceptance Criteria / Definition of Done

Each Low-Level Task below maps to a Mid-Level Objective. A task is **Done** when:

1. All specified acceptance criteria are checkable and passing.
2. The implementation does not introduce any float/double type in the money path.
3. All new DB queries use parameterized statements.
4. The change produces a structured audit log event for each state transition.
5. Unit tests cover the happy path, the identified edge cases, and all failure branches.
6. Integration test uses a real DB (not mocked) for any test involving ledger writes.

---

## Data Retention Policy

**Retention period: 7 years** from the date of record creation, unless a specific regulation mandates longer.

| Record Type | Hot Storage | Cold Archive | Deletion |
|---|---|---|---|
| `ledger_entries` | Years 1–2 (primary DB) | Years 3–7 (S3 Parquet via Athena) | Delete at 7 years + 1 day |
| `transfers` | Years 1–2 | Years 3–7 | Delete at 7 years + 1 day |
| `audit_log` | 1 year (primary DB) | Years 2–7 (S3; WORM-locked) | Delete at 7 years + 1 day |
| `compliance_events` (SAR/CTR) | 5 years minimum (FinCEN BSA) | Years 6–7 | Delete at 7 years |
| KYC records (Persona inquiry data) | Duration of account | Per Persona DPA | Delete at account closure + 5 years, or 7 years whichever is later |
| User PII (`users` table) | Active account | Closed account + 7 years | GDPR/CCPA erasure requests: pseudonymize non-financial fields; retain financial records for legal hold |
| `idempotency_keys` | 24 hours (Redis TTL) | Not archived | Auto-expired by Redis TTL |

**Archival mechanism:** A nightly job (`ArchivalJob`) moves rows older than 2 years from `ledger_entries` and `transfers` to S3 as Parquet files, queryable via AWS Athena. After successful S3 write verification, rows are deleted from the primary DB. The Athena table schema mirrors the PostgreSQL schema exactly.

**Legal hold:** A `legal_holds` table flags user IDs whose records must not be deleted regardless of retention schedule. The archival and deletion jobs check this table before acting.

**Compliance basis:** 7-year retention covers: FinCEN BSA 5-year minimum (31 CFR 1010.430), IRS record-keeping (IRC § 6501 statute of limitations), and typical US civil litigation limitation periods (most states: 6 years for breach of contract).

---

## Implementation Notes

- **Node.js version:** 22 LTS (ESM modules; `strict` TypeScript)
- **Database:** PostgreSQL 16; use `pg` driver with connection pooling via `pg-pool`; all ledger writes in SERIALIZABLE isolation
- **gRPC:** `@grpc/grpc-js` + `@grpc/proto-loader`
- **Frontend:** React 19 + TypeScript; no monetary calculations on the frontend; amounts displayed by dividing stored cents by 100 using `Intl.NumberFormat`
- **Testing:** Jest for unit; Supertest for HTTP integration; a real PostgreSQL instance in Docker for integration tests (no mocks on DB layer)
- **Environment:** All secrets via AWS Secrets Manager; no `.env` files committed to source control
- **Money formatting:** Amounts are always transmitted as integers over the wire; the frontend formats for display only

---

## Context

### Beginning Context

| Artifact | State |
|----------|-------|
| PostgreSQL 16 | Running; empty schema |
| Node.js 22 | Available; empty project |
| React 19 | Available; empty project |
| Stripe account | Test mode; API keys in Secrets Manager |
| Plaid account | Sandbox; API keys in Secrets Manager |
| Persona account | Sandbox; API key in Secrets Manager |
| AWS infrastructure | VPC, RDS, ElastiCache (Redis), ECS clusters provisioned |
| `transfers` table | Does not exist |
| `ledger_entries` table | Does not exist |

### Ending Context

| Artifact | State |
|----------|-------|
| `src/backend/db/migrations/` | All schema migrations applied and verified |
| `src/backend/services/TransferService.ts` | Implements `InitiateTransfer`, `GetTransfer`, `ListTransfers` |
| `src/backend/services/WalletService.ts` | Implements `FundWallet`, `GetBalance`, `WithdrawFunds` |
| `src/backend/services/KycService.ts` | Implements `StartKyc`, `HandlePersonaWebhook` |
| `src/backend/services/FeeService.ts` | Implements `calculateTransferFee`, `getMtdTransferVolume` |
| `src/backend/services/HandleService.ts` | Implements `registerHandle`, `lookupByHandle` |
| `src/backend/services/WithdrawalService.ts` | Implements `initiateWithdrawal` + Stripe payout webhook handler |
| `src/backend/routes/payments/**/*` | Express/gRPC route handlers; all guarded by `UserGuard` |
| `src/backend/jobs/ReconciliationJob.ts` | Nightly ledger integrity check |
| `src/backend/jobs/ArchivalJob.ts` | Nightly 2-year archival to S3 Parquet |
| `src/frontend/components/TransferFlow/` | Complete P2P transfer UI |
| `tests/integration/` | Full integration test suite against real DB |
| `tests/unit/` | Unit tests for all service functions |

---

## Low-Level Tasks

### Task 1 — Database Schema Migration: Users & Wallets
**Serves:** MLO-3, MLO-4, MLO-6

**Prompt:** Create a database migration that defines the `users`, `wallets`, `user_status` enum, and `wallets.balance_cents` with a `CHECK (balance_cents >= 0)` constraint.

**File:** `src/backend/db/migrations/001_users_wallets.sql`

**Acceptance Criteria:**
- [ ] `user_status` enum contains all 8 states defined in B.1.1
- [ ] `wallets.balance_cents` is `BIGINT NOT NULL DEFAULT 0` with `CHECK (balance_cents >= 0)`
- [ ] No `NUMERIC`, `FLOAT`, or `DECIMAL` type appears in the file
- [ ] Migration is idempotent (`IF NOT EXISTS` guards on all `CREATE` statements)
- [ ] Migration verified by running `psql -f 001_users_wallets.sql` against a blank DB with exit code 0

---

### Task 2 — Database Schema Migration: Transfer Ledger
**Serves:** MLO-1, MLO-4, MLO-5

**Prompt:** Create a migration defining `transfers`, `ledger_entries`, `transfer_status` enum, immutability rules, and the `idempotency_keys` table.

**File:** `src/backend/db/migrations/002_transfers_ledger.sql`

**Acceptance Criteria:**
- [ ] `ledger_entries` has `CREATE RULE no_update_ledger` and `CREATE RULE no_delete_ledger`
- [ ] `ledger_entries.chain_hash` is `BYTEA NOT NULL`
- [ ] `transfers.idempotency_key` has a `UNIQUE` constraint
- [ ] `transfers.amount_cents` has `CHECK (amount_cents > 0)`
- [ ] Attempting `UPDATE ledger_entries` in `psql` has no effect (rule silently suppresses it)

---

### Task 3 — Idempotency Middleware
**Serves:** MLO-2

**Prompt:** Implement Express middleware that reads `x-idempotency-key` from request headers, validates it is a UUID v4, checks the `idempotency_keys` table (Redis cache first, DB fallback), and either replays the cached response or passes through to the handler and stores the response on the way out.

**File:** `src/backend/middleware/idempotency.ts`

**Acceptance Criteria:**
- [ ] Missing `x-idempotency-key` returns HTTP 400 with `{ "code": "MISSING_IDEMPOTENCY_KEY" }`
- [ ] Non-UUID v4 key returns HTTP 400 with `{ "code": "INVALID_IDEMPOTENCY_KEY_FORMAT" }`
- [ ] Replayed request returns the original HTTP status code and body, not a new execution
- [ ] Two concurrent requests with the same key: only one executes; the other waits and receives the same response (Redis distributed lock with 30-second TTL)
- [ ] Integration test: submit same transfer twice with same idempotency key; assert exactly one `ledger_entries` row created

---

### Task 4 — UserGuard Middleware (KYC Status Gate)
**Serves:** MLO-3

**Prompt:** Implement `UserGuard` middleware that reads the authenticated user's status from Redis cache (30s TTL), falls back to DB read, and rejects any request to a financial endpoint if status is not `VERIFIED`.

**File:** `src/backend/middleware/userGuard.ts`

**Acceptance Criteria:**
- [ ] User with status `PROVISIONAL` calling `POST /transfers` receives HTTP 403 with `{ "code": "KYC_REQUIRED" }`
- [ ] User with status `FROZEN` receives HTTP 403 with `{ "code": "ACCOUNT_FROZEN" }`
- [ ] User with status `VERIFIED` passes through
- [ ] Cache is invalidated on `user.status` change (publish to Redis pub/sub channel)
- [ ] Unit test covers all 8 user status states

---

### Task 5 — Transfer Service: InitiateTransfer
**Serves:** MLO-1, MLO-2, MLO-4, MLO-5

**Prompt:** Implement the `InitiateTransfer` function: validate inputs, run all pre-condition checks, acquire wallet locks in consistent key order, write debit + credit ledger entries with chain hashes, update wallet balances, and commit — all inside a SERIALIZABLE transaction.

**File:** `src/backend/services/TransferService.ts`

**Functions:** `initiateTransfer(params: InitiateTransferParams): Promise<TransferResponse>`

**Acceptance Criteria:**
- [ ] All DB operations use a single `BEGIN ISOLATION LEVEL SERIALIZABLE` / `COMMIT` block
- [ ] Wallet locks are acquired in ascending `wallet_id` UUID order (prevents deadlock)
- [ ] `chain_hash` for each ledger entry is `SHA-256(previous_chain_hash || entry_data)` where `entry_data` is the canonical JSON of the entry
- [ ] Transfer to a `FROZEN` recipient returns `{ "code": "RECIPIENT_FROZEN" }` before any DB write
- [ ] Concurrent test: 100 simultaneous transfers from same sender; assert final balance = initial_balance − (amount × number_of_successful_transfers); no negative balance; no duplicate ledger entries
- [ ] No `float` or `number` type used for `amount_cents` arithmetic; must use `BigInt`

---

### Task 6 — Transfer Service: Ledger Chain Hash
**Serves:** MLO-5

**Prompt:** Implement the chain hash calculation function that produces a SHA-256 hash chaining each new ledger entry to its predecessor for tamper evidence.

**File:** `src/backend/services/LedgerService.ts`

**Functions:** `computeChainHash(prevHash: Buffer, entry: LedgerEntryData): Buffer`

**Acceptance Criteria:**
- [ ] First entry in a wallet uses a genesis hash: `SHA-256("GENESIS")`
- [ ] Hash input is `SHA-256(prevHash || wallet_id || entry_type || amount_cents || created_at_iso)` with canonical encoding (no whitespace variation)
- [ ] Unit test: given known inputs, output matches a pre-computed expected hash
- [ ] Reconciliation function `verifyChain(walletId: string)` re-computes and verifies every hash in order; returns `{ valid: true }` or `{ valid: false, brokenAt: entryId }`

---

### Task 7 — Stripe Webhook Handler
**Serves:** MLO-1, MLO-6

**Prompt:** Implement the Stripe webhook endpoint that verifies the Stripe signature, handles `payment_intent.succeeded` and `payment_intent.payment_failed` events, and idempotently updates the corresponding transfer record and inserts ledger entries on success.

**File:** `src/backend/routes/payments/stripeWebhook.ts`

**Acceptance Criteria:**
- [ ] Webhook with invalid signature returns HTTP 400; no DB write occurs
- [ ] `payment_intent.succeeded` for an already-CLEARED transfer is a no-op (idempotent)
- [ ] Amount in webhook event is validated against `transfers.amount_cents`; mismatch triggers P1 alert and returns HTTP 400
- [ ] Raw webhook body is verified using `stripe.webhooks.constructEvent` before any JSON parsing of business fields
- [ ] Integration test: replay a captured Stripe test webhook; assert transfer status = CLEARED and ledger has exactly 2 entries (debit from funding source, credit to wallet)

---

### Task 8 — Persona KYC Webhook Handler
**Serves:** MLO-3

**Prompt:** Implement the Persona webhook handler that verifies the signature, maps inquiry status to our `user_status` enum, and atomically updates user status + creates a compliance event.

**File:** `src/backend/routes/kyc/personaWebhook.ts`

**Acceptance Criteria:**
- [ ] `inquiry.approved` → `user.status = VERIFIED`; wallet created atomically in same transaction
- [ ] `inquiry.declined` → `user.status = KYC_FAILED`; compliance event inserted
- [ ] `inquiry.needs_review` → `user.status = KYC_REVIEW`; ops ticket created via internal ticketing API
- [ ] Signature verification failure → HTTP 401; no state change
- [ ] Redis cache for user status is invalidated after status change
- [ ] Duplicate webhook (same `inquiry_id`) is idempotent

---

### Task 9 — AML Velocity Check
**Serves:** MLO-3

**Prompt:** Implement the AML velocity check that counts transfers in the last 60-minute rolling window for a sender and enforces the ≤10 transfer limit.

**File:** `src/backend/services/AmlService.ts`

**Functions:** `checkTransferVelocity(userId: string, amount_cents: bigint): Promise<VelocityCheckResult>`

**Acceptance Criteria:**
- [ ] Uses a single SQL query: `SELECT COUNT(*) FROM transfers WHERE sender_wallet_id = $1 AND created_at > now() - INTERVAL '60 minutes' AND status != 'FAILED'`
- [ ] Count ≥ 10 returns `{ allowed: false, reason: "VELOCITY_LIMIT_EXCEEDED" }`
- [ ] Temporal boundary is strictly enforced: the 61st-minute transfer is allowed
- [ ] Unit test with mocked DB returning count = 9, 10, 11; verify boundary behavior
- [ ] AML check occurs before any wallet lock acquisition in `InitiateTransfer`

---

### Task 10 — Nightly Reconciliation Job
**Serves:** MLO-1, MLO-5, MLO-7

**Prompt:** Implement a scheduled job (cron: `0 2 * * *`) that verifies the ledger balance invariant for every wallet and the chain hash integrity for every ledger sequence.

**File:** `src/backend/jobs/ReconciliationJob.ts`

**Acceptance Criteria:**
- [ ] For each wallet: `computed_balance = SUM(CREDIT) − SUM(DEBIT)` must equal `wallet.balance_cents`; any mismatch emits a P0 alert to PagerDuty and writes a `reconciliation_failures` record
- [ ] Chain hash verification runs for every wallet in parallel (worker pool, max 10 concurrent)
- [ ] Job completion time is recorded; if job duration > 4 hours, alert fires
- [ ] Dry-run mode (`--dry-run` flag): runs all checks, writes report, sends no alerts
- [ ] Integration test: inject one corrupted chain hash; assert job detects and reports it

---

### Task 11 — Money String Validation Utility
**Serves:** MLO-4

**Prompt:** Implement the input money string validation and conversion utility that parses user-facing dollar strings into integer cents with strict validation.

**File:** `src/backend/utils/money.ts`

**Functions:** `parseToCents(input: string, currency: 'USD'): bigint`

**Acceptance Criteria:**
- [ ] `"10.00"` → `1000n`
- [ ] `"10.5"` → `1050n`
- [ ] `"10"` → `1000n`
- [ ] `"10.001"` → throws `MoneyParseError("too many decimal places")`
- [ ] `"-5.00"` → throws `MoneyParseError("negative amount not allowed")`
- [ ] `"1e5"` → throws `MoneyParseError("scientific notation not allowed")`
- [ ] `""` → throws `MoneyParseError("empty input")`
- [ ] Uses no `parseFloat` or `Number()`; uses string splitting on `.` only
- [ ] 100% unit test coverage on all branches

---

### Task 13 — Handle Registration & Lookup Service
**Serves:** MLO-1, MLO-3

**Prompt:** Implement handle registration (validation + uniqueness check) during onboarding and a handle lookup endpoint used by the transfer flow to resolve a `@handle` to a `user_id`.

**File:** `src/backend/services/HandleService.ts`, `src/backend/routes/users/handleLookup.ts`

**Functions:** `registerHandle(userId: string, handle: string)`, `lookupByHandle(handle: string): Promise<PublicUserProfile>`

**Acceptance Criteria:**
- [ ] Handle validation regex: `/^[a-zA-Z0-9_]{3,20}$/` — any other character returns `INVALID_HANDLE_FORMAT`
- [ ] Lookup is case-insensitive: `@John_Doe` and `@john_doe` resolve to the same user
- [ ] Handle stored normalized as `lower(handle)` in DB but display handle preserves original casing
- [ ] `lookupByHandle` returns only `{ user_id, display_handle, display_name }` — no email, phone, or status
- [ ] Lookup of a non-VERIFIED user returns `RECIPIENT_NOT_FOUND` (same error as truly missing handle — prevents enumeration)
- [ ] Handle change after registration: not allowed in MVP; endpoint returns `HANDLE_IMMUTABLE`
- [ ] DB: `CREATE UNIQUE INDEX ON users (lower(handle))`
- [ ] Unit test: valid handles, handle with spaces (fail), handle too short (fail), handle with emoji (fail), case-insensitive round-trip

---

### Task 14 — Fee Calculation Service
**Serves:** MLO-4 (integer arithmetic), MLO-1 (fee debited in same transaction)

**Prompt:** Implement the transfer fee calculation service that computes the fee for a given transfer amount given the sender's MTD transfer volume, using integer arithmetic and Bankers' Rounding for the percentage calculation.

**File:** `src/backend/services/FeeService.ts`

**Functions:** `calculateTransferFee(amountCents: bigint, mtdVolumeCents: bigint): bigint`, `getMtdTransferVolume(walletId: string, client: PoolClient): Promise<bigint>`

**Acceptance Criteria:**
- [ ] `calculateTransferFee(100000n, 0n)` = `0n` (within $2,000 free tier, $1,000 transfer)
- [ ] `calculateTransferFee(100000n, 200000n)` = `2000n` (fully above tier, $1,000 × 2% = $20.00)
- [ ] `calculateTransferFee(150000n, 150000n)` = `1000n` (half above tier: $500 × 2% = $10.00)
- [ ] `calculateTransferFee(1n, 199999n)` = `0n` (1 cent entirely within remaining free allowance)
- [ ] Bankers' Rounding: `calculateTransferFee(2500n, 200000n)` = `50n` ($25.00 × 2% = $0.50 — rounds to even 50 cents)
- [ ] No `parseFloat`, `Number()`, `Math.round()` in implementation
- [ ] `getMtdTransferVolume` accepts a `PoolClient` (not the pool) so it runs inside the caller's transaction
- [ ] Unit tests for: fully free, fully paid, split-tier, Bankers' Rounding boundary, zero-amount guard

---

### Task 15 — Withdrawal Service (Stripe Instant Payouts)
**Serves:** MLO-1, MLO-4, MLO-6

**Prompt:** Implement the withdrawal flow: validate the debit card PaymentMethod, calculate the 1% Stripe Instant Payout fee, debit the wallet (full amount including fee), call Stripe `/v1/payouts`, and handle `payout.paid` / `payout.failed` webhooks with compensating entries on failure.

**File:** `src/backend/services/WithdrawalService.ts`, `src/backend/routes/payments/stripePayoutWebhook.ts`

**Functions:** `initiateWithdrawal(params: WithdrawalParams): Promise<TransferResponse>`

**Acceptance Criteria:**
- [ ] Debit card check: `paymentMethod.card.funding !== 'debit'` returns `INVALID_PAYOUT_DESTINATION` before any DB write
- [ ] Minimum withdrawal: `amount_cents < 100n` returns `WITHDRAWAL_AMOUNT_TOO_SMALL`
- [ ] Maximum withdrawal: `amount_cents > 1000000n` returns `WITHDRAWAL_AMOUNT_EXCEEDS_LIMIT`
- [ ] Full wallet debit (amount + fee) occurs in same SERIALIZABLE transaction as ledger entries, before the Stripe API call
- [ ] If Stripe API call fails after DB commit: transfer status = PENDING; a background retry job attempts the Stripe call up to 3 times before marking FAILED and issuing compensating entries
- [ ] `payout.failed` webhook: compensating CREDIT entries for both `withdrawal_amount_cents` and `payout_fee_cents` in one atomic transaction
- [ ] Fee calculation: `payout_fee_cents = round_half_even(amount_cents × 100 / 10000)` (1% = 100 bps)
- [ ] Integration test: initiate withdrawal → mock Stripe payout.failed webhook → assert wallet balance fully restored, status = FAILED

---

### Task 16 — Data Archival Job
**Serves:** MLO-5, MLO-7

**Prompt:** Implement the nightly archival job that moves `ledger_entries` and `transfers` rows older than 2 years to S3 as Parquet files and deletes them from the primary DB, respecting legal holds.

**File:** `src/backend/jobs/ArchivalJob.ts`

**Acceptance Criteria:**
- [ ] Processes records in batches of 10,000 rows to avoid long-running transactions
- [ ] For each batch: write Parquet to S3 at `s3://{BUCKET}/archive/{table}/{year}/{month}/batch_{id}.parquet`, verify S3 object exists and matches row count, then delete from DB
- [ ] Records for users in `legal_holds` table are skipped (not deleted) regardless of age
- [ ] Job is idempotent: re-running after a partial failure re-processes only rows not yet in S3 (tracked via `archived_at` timestamp column)
- [ ] Job duration recorded in `job_runs` table; alert if > 6 hours
- [ ] Dry-run mode (`--dry-run`): writes report of what would be archived; no S3 writes, no deletes
- [ ] Integration test: seed 15,000 rows older than 2 years; run job; assert DB has 0 such rows; assert S3 has 2 Parquet files; assert 1 legal-hold user's rows were skipped

---

### Task 17 — Frontend Transfer Flow Component
**Serves:** MLO-1, MLO-3

**Prompt:** Implement the React `<TransferFlow>` component that collects recipient identifier, amount (as a dollar string), and optional memo, validates inputs client-side, generates a UUID v4 idempotency key, and submits to the transfer API.

**File:** `src/frontend/components/TransferFlow/TransferFlow.tsx`

**Acceptance Criteria:**
- [ ] Amount displayed using `Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' })`
- [ ] Amount transmitted to backend as `amount_cents: number` (integer, not float string)
- [ ] Idempotency key generated with `crypto.randomUUID()` on component mount; same key used if user retries without refreshing
- [ ] On `RECIPIENT_FROZEN` error: display "This recipient's account is temporarily unavailable." — do not expose freeze reason
- [ ] On `INSUFFICIENT_FUNDS` error: display current balance and amount attempted
- [ ] No monetary arithmetic in component; all calculations delegated to backend

---
