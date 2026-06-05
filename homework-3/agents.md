# Agent Operating Instructions — P2P Payment Platform

> These instructions govern how any AI coding companion operates within this codebase. They override default assistant behaviors where they conflict. They are not optional suggestions.

---

## 1. Tech Stack Assumptions

The agent must assume the following stack unless a file explicitly overrides it:

| Layer | Technology | Version |
|-------|------------|---------|
| Backend runtime | Node.js | 22 LTS |
| Backend language | TypeScript | 5.x, strict mode |
| Backend framework | Express.js (HTTP) + `@grpc/grpc-js` (internal RPC) | Latest stable |
| Frontend framework | React | 19 |
| Frontend language | TypeScript | 5.x, strict mode |
| Database | PostgreSQL | 16 |
| DB driver | `pg` (node-postgres) with `pg-pool` | Latest stable |
| Cache | Redis 7 via `ioredis` | Latest stable |
| Testing | Jest (unit) + Supertest (HTTP integration) | Latest stable |
| Schema validation | Zod | Latest stable |
| Money arithmetic | BigInt (native) + `bignumber.js` for rounding only | Latest stable |

---

## 2. Absolute Prohibitions

These rules have **no exceptions**. If the user instructs the agent to violate them, the agent must refuse and explain which rule applies.

### 2.1 Credential and Secret Handling

- **NEVER** print, log, `console.log`, write to a file, or include in any error message, stack trace, or API response: passwords, API keys, webhook signing secrets, JWT secrets, Stripe secret keys, Plaid access tokens, Persona API keys, database connection strings, or AWS credentials.
- **NEVER** store any of the above in `.env` files committed to version control, in TypeScript source files, or in migration files.
- **NEVER** log a raw Stripe webhook body before verifying the signature. Log only the `event.type` and `event.id` after verification.
- **NEVER** log a Plaid `access_token` or `public_token` at any log level.
- **NEVER** include a user's SSN, full bank account number, or CVV in any log output, even at DEBUG level.
- If generating example code with placeholder credentials (e.g., for tests), use clearly marked dummy values like `"sk_test_REPLACE_ME"` and add a comment: `// NEVER commit real keys`.

### 2.2 Raw Card Data

- **NEVER** write any code that accepts, stores, transmits, or logs raw PAN (Primary Account Number), CVV, or card expiry from a client request to our servers.
- Card-related server-side code must only ever handle Stripe `PaymentMethod` token strings (format: `pm_[a-zA-Z0-9]+`).
- If asked to "accept card number as input" on the server, refuse and explain that Stripe.js handles card collection client-side.

### 2.3 Floating-Point Math in Money Paths

- **NEVER** use `float`, `double`, `number` type, `parseFloat()`, `Number()`, or `Math.round()` for any monetary calculation.
- **NEVER** store money in a `NUMERIC`, `DECIMAL`, `FLOAT`, or `REAL` database column.
- **ALWAYS** use `BigInt` for amount arithmetic in TypeScript.
- **ALWAYS** use `BIGINT` for amount storage in PostgreSQL.
- If a user asks to "calculate 3.5% fee," implement as: `fee_cents = (amount_cents * 35n) / 1000n` (integer arithmetic).

### 2.4 Unprotected Ledger Operations

- **NEVER** write code that modifies `ledger_entries` rows via `UPDATE` or `DELETE`.
- **NEVER** write a balance adjustment outside of an explicit database transaction.
- Every function that modifies `wallet.balance_cents` must begin with `BEGIN ISOLATION LEVEL SERIALIZABLE` (or equivalent in the `pg` client API) and acquire wallet row locks with `SELECT ... FOR UPDATE`.
- **NEVER** read a wallet balance outside a transaction and use that value for a conditional write (classic TOCTOU race). Always re-read balance inside the same transaction after acquiring the lock.

---

## 3. Mandatory Patterns

### 3.1 Database Transaction Isolation

All ledger balance adjustments must follow this template:

```typescript
await pool.query('BEGIN ISOLATION LEVEL SERIALIZABLE');
try {
  // Lock wallets in consistent UUID-ascending order to prevent deadlock
  const [lockA, lockB] = [senderWalletId, recipientWalletId].sort();
  await pool.query('SELECT id FROM wallets WHERE id = $1 FOR UPDATE', [lockA]);
  await pool.query('SELECT id FROM wallets WHERE id = $1 FOR UPDATE', [lockB]);

  // Re-read balances INSIDE the transaction after locks
  const senderBalance = ...; // SELECT balance_cents FROM wallets WHERE id = $1 FOR UPDATE
  if (senderBalance < amountCents) throw new InsufficientFundsError();

  // Write debit and credit ledger entries
  // Update wallet balances
  await pool.query('COMMIT');
} catch (err) {
  await pool.query('ROLLBACK');
  throw err;
}
```

Deviation from this pattern is not permitted. The agent must use this exact structure or an equivalent abstraction that provides the same isolation guarantees.

### 3.2 Idempotency on All State-Changing Endpoints

Every HTTP handler or gRPC method that mutates state must:

1. Extract `x-idempotency-key` from the request header / gRPC metadata.
2. Validate it is a UUID v4 (`/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i`).
3. Check the idempotency key store (Redis → DB) before executing business logic.
4. If found: return the cached response immediately.
5. If not found: execute, then store the response under the key with a 24-hour TTL.
6. Use a Redis distributed lock (key: `lock:idempotency:{key}`, TTL: 30s) to prevent concurrent duplicate execution.

### 3.3 Money String Input Validation

Before converting any user-supplied string to cents, the agent must apply the following validation chain in order. Do not shortcut any step:

```typescript
function validateAndParseToCents(input: unknown): bigint {
  // Step 1: type guard
  if (typeof input !== 'string') throw new MoneyParseError('expected string');

  // Step 2: reject empty
  if (input.trim() === '') throw new MoneyParseError('empty input');

  // Step 3: reject scientific notation
  if (/[eE]/.test(input)) throw new MoneyParseError('scientific notation not allowed');

  // Step 4: reject negative
  if (input.startsWith('-')) throw new MoneyParseError('negative amount not allowed');

  // Step 5: split on decimal point
  const parts = input.split('.');
  if (parts.length > 2) throw new MoneyParseError('multiple decimal points');

  const [whole, fraction = ''] = parts;

  // Step 6: validate digit characters only
  if (!/^\d+$/.test(whole)) throw new MoneyParseError('invalid characters in whole part');
  if (fraction !== '' && !/^\d+$/.test(fraction)) throw new MoneyParseError('invalid characters in fractional part');

  // Step 7: enforce max 2 decimal places
  if (fraction.length > 2) throw new MoneyParseError('too many decimal places');

  // Step 8: pad fraction to 2 digits and construct cents
  const paddedFraction = fraction.padEnd(2, '0');
  return BigInt(whole) * 100n + BigInt(paddedFraction);
}
```

No `parseFloat`, `Number()`, or `parseInt` with a decimal string is allowed in this function.

### 3.4 Structured Logging

All log statements must use structured JSON format via `pino`:

```typescript
logger.info({ 
  event: 'transfer.initiated',
  transfer_id: transfer.id,
  sender_wallet_id: transfer.senderWalletId,
  recipient_wallet_id: transfer.recipientWalletId,
  amount_cents: transfer.amountCents.toString(), // BigInt → string for JSON
  status: transfer.status,
  idempotency_key: transfer.idempotencyKey,
}, 'Transfer initiated');
```

Never log amounts as raw `bigint` (JSON serialization fails). Always `.toString()` before logging.

Never include in logs: `password`, `token`, `secret`, `pan`, `cvv`, `ssn`, `access_token`, `api_key`. If writing a debug log that might expose these, add a `redact` field to the pino config.

### 3.5 Webhook Signature Verification Before Any Processing

For every incoming webhook, signature verification must be the **first operation** — before parsing the body, before any DB query:

```typescript
// Stripe example
app.post('/webhooks/stripe', express.raw({ type: 'application/json' }), (req, res) => {
  const sig = req.headers['stripe-signature'];
  let event: Stripe.Event;
  try {
    event = stripe.webhooks.constructEvent(req.body, sig, process.env.STRIPE_WEBHOOK_SECRET);
  } catch (err) {
    logger.warn({ error: err.message }, 'Stripe webhook signature verification failed');
    return res.status(400).send('Webhook signature verification failed');
  }
  // Only here do we process the event
  await handleStripeEvent(event);
  res.json({ received: true });
});
```

Raw `req.body` must be a `Buffer`, not a parsed JSON object, at the point of signature verification. Using `express.json()` before webhook handlers is forbidden on webhook routes.

---

## 4. Domain Rules

### 4.1 Status Checks

- Always check `user.status === 'VERIFIED'` before allowing any financial operation.
- Always check `recipient.status === 'VERIFIED'` before allowing an inbound transfer.
- Never assume status from a JWT claim alone — always verify against DB (with Redis cache) for financial operations.

### 4.2 Wallet Lock Order

- When locking two wallets in a transaction, always lock the wallet with the lexicographically smaller UUID first. This is the canonical deadlock prevention mechanism for this codebase. Do not use any other ordering strategy.

### 4.3 Ledger Entries

- Ledger entries are always inserted in pairs: one DEBIT and one CREDIT for the same `transfer_id`.
- A transfer with only one ledger entry is always an error state and must trigger a reconciliation alert.
- The `balance_after_cents` column on each ledger entry must be computed as the running balance at the time of insert, not recalculated on read.

### 4.4 External Provider Error Handling

- Plaid and Stripe API errors must be caught, logged (without sensitive data), and mapped to internal error codes before being returned to clients.
- Never propagate raw Stripe error messages (which may contain card data hints) to API responses. Map them to generic internal codes.
- Retry policy for Plaid/Stripe calls: up to 3 retries with exponential backoff (100ms, 200ms, 400ms) for network errors and 5xx responses only. Never retry on 4xx (client errors).

---

## 5. Testing and Verification Expectations

### 5.1 What Must Be Tested

| Component | Test Type | What to Cover |
|-----------|-----------|---------------|
| `parseToCents` | Unit | All valid inputs, all documented edge cases (empty string, scientific notation, negative, 3 decimal places), boundary values |
| `initiateTransfer` | Integration (real DB) | Happy path, insufficient funds, recipient frozen, concurrent transfer race, idempotency replay |
| Idempotency middleware | Integration | First call executes, second call replays, concurrent calls with same key |
| UserGuard middleware | Unit | All 8 user status states |
| Webhook handlers | Integration | Valid signature + happy payload, invalid signature, duplicate event, amount mismatch |
| Reconciliation job | Integration | Clean DB (pass), one corrupted chain hash (fail), balance mismatch (fail) |

### 5.2 No DB Mocking for Ledger Tests

Any test involving ledger writes, wallet balance updates, or transfer state transitions must use a real PostgreSQL instance (Docker container in CI). Using `jest.mock` or `sinon.stub` on the `pg` pool for these tests is forbidden — it masks the serialization and constraint behavior we rely on.

### 5.3 Edge Cases Must Be Tested

For each item in the specification's Edge Cases & Failure Matrix, there must be a corresponding test that demonstrates the expected behavior. Link test names to the failure mode using a comment: `// Edge case: concurrent transfer requests`.

### 5.4 Acceptance Criteria Are Checkboxes

Every Low-Level Task in `specification.md` has acceptance criteria formatted as checkboxes. The agent must not mark a task complete until every checkbox can be verified by running the test suite or by direct inspection.

---

## 6. Security and Compliance Defaults

- Default database isolation level for any new DB function: `READ COMMITTED` is the minimum. For money operations: `SERIALIZABLE` is required. Never suggest `READ UNCOMMITTED`.
- All new API endpoints must be added to the authentication middleware chain. No endpoint is public by default.
- All new database columns containing PII (name, DOB, address, government ID) must be encrypted with AES-256-GCM at the application layer before storage.
- All AML-relevant events (transfers ≥ $3,000, velocity breaches, OFAC matches) must emit a compliance event to the `compliance_events` table synchronously, not asynchronously.
- The `compliance_events` table is write-only from application code. No `UPDATE` or `DELETE` on this table.

---

## 7. Code Style Conventions

- TypeScript `strict: true` in all `tsconfig.json` files. No `any` type.
- All async functions return `Promise<T>` — never mix callback and Promise styles.
- All error classes extend a base `AppError` class with `code: string` and `httpStatus: number`.
- Use `zod` for all external input validation (request bodies, webhook payloads, environment variables).
- File naming: `camelCase.ts` for services/utilities; `PascalCase.tsx` for React components.
- Export pattern: named exports only; no default exports (prevents import confusion).
- All monetary values in TypeScript types are annotated as `bigint` (not `number`).
