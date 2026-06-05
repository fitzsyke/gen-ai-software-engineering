# Claude Code Workspace Rules — P2P Payment Platform

> These rules configure Claude Code's behavior within this project. They apply to all files matching the specified glob patterns and establish hard constraints for AI-assisted development in a PCI-DSS Level 1-regulated environment.

---

## Global Rules (All Files)

### Never Suggest These Patterns

- `parseFloat()`, `Number()`, `Math.round()`, `Math.floor()`, `Math.ceil()` applied to monetary strings or values.
- `NUMERIC`, `DECIMAL`, `FLOAT`, `REAL` as column types in any SQL migration.
- `console.log`, `console.error`, `console.debug` — use `pino` logger only.
- `process.env.SECRET_KEY` or any direct environment variable access for secrets — use the `SecretsManager` utility from `src/backend/config/secrets.ts`.
- `any` as a TypeScript type annotation.
- String interpolation in SQL queries: e.g. `` `SELECT * FROM users WHERE id = '${userId}'` `` — use parameterized queries exclusively.
- `Math.random()` for generating idempotency keys, session tokens, or any security-relevant identifier — use `crypto.randomUUID()` or `crypto.getRandomValues()`.

### Always Suggest These Patterns

- `BigInt` literals (e.g., `1000n`) and `BigInt()` constructor for all monetary values.
- Parameterized SQL: `pool.query('SELECT * FROM users WHERE id = $1', [userId])`.
- `zod` schema validation on all incoming data before any business logic.
- `pino` structured logging with the schema: `logger.info({ event: '...', ...fields }, 'message')`.
- `crypto.randomUUID()` for generating all UUIDs client- and server-side.

---

## File Glob: `src/backend/routes/payments/**/*`

**Context:** These files are the highest-risk surface area of the application — they handle money movement, external provider webhooks, and cardholder-proximate data.

### Rules for Payment Route Files

1. **Every route handler must be wrapped by these middleware in order:**
   ```
   authMiddleware → userGuard → idempotencyMiddleware → rateLimit → handler
   ```
   If any middleware is missing, flag it as a compliance gap.

2. **Webhook routes are the exception:** Webhook routes (`/webhooks/stripe`, `/webhooks/plaid`, `/webhooks/persona`) must use `express.raw()` body parser (not `express.json()`) and must begin with signature verification before any other processing.

3. **No business logic in route handlers:** Route handlers must be thin wrappers that call a service function. Business logic (balance checks, ledger writes, AML checks) belongs in `src/backend/services/`.

4. **Error responses must never include:**
   - Raw PostgreSQL error messages (may leak schema details)
   - Stack traces (in production)
   - Raw external provider error messages from Stripe/Plaid
   - Any user PII beyond the requesting user's own masked data

5. **Amount handling:** Any `amount` field arriving in a request body must be immediately passed through `validateAndParseToCents()` from `src/backend/utils/money.ts` before any use. Never use the raw string or float value.

6. **Required response fields for transfer endpoints:**
   ```typescript
   {
     transfer_id: string,       // UUID
     status: TransferStatus,
     amount_cents: number,      // integer, not float
     currency: string,          // ISO 4217
     created_at: string,        // ISO 8601
   }
   ```

### Auto-Checks for Generated Migrations in `src/backend/db/migrations/**/*`

When generating or reviewing a database migration file, Claude Code must verify the following automatically:

#### Mandatory Migration Checks

| Check | Rule | How to Verify |
|-------|------|---------------|
| No float money columns | No column definition contains `NUMERIC`, `FLOAT`, `REAL`, `DOUBLE PRECISION` | grep for these types; fail if found in a money-adjacent table |
| Integer money columns | All amount columns use `BIGINT` | confirm with column definition |
| Non-negative balance constraint | `wallets.balance_cents` has `CHECK (balance_cents >= 0)` | look for the CHECK constraint |
| Idempotency key uniqueness | `transfers.idempotency_key` has `UNIQUE` constraint | look for UNIQUE constraint or index |
| Ledger immutability rules | `ledger_entries` table has `CREATE RULE no_update_ledger` and `CREATE RULE no_delete_ledger` | look for both rules |
| Chain hash column | `ledger_entries.chain_hash` is `BYTEA NOT NULL` | look for column definition |
| Migration idempotency | All `CREATE TABLE` statements use `IF NOT EXISTS` | grep for CREATE TABLE without IF NOT EXISTS |
| No secrets in migration | Migration contains no hardcoded passwords, API keys, or credentials | scan for patterns matching known secret formats |
| Rollback script present | Each `up` migration has a corresponding `down` migration section or file | check for both directions |

If any check fails, surface it as an inline comment before the migration content and do not proceed with applying the migration.

#### Migration File Naming Convention

Migration files must follow: `{NNN}_{verb}_{noun}.sql` where:
- `NNN` is a zero-padded 3-digit sequence number (e.g., `001`, `002`)
- `verb` is one of: `create`, `add`, `alter`, `drop`, `index`
- `noun` is the primary table or concept

Example: `003_create_compliance_events.sql`

---

## File Glob: `src/backend/services/**/*`

**Context:** Service files contain the core business logic including ledger operations, KYC state machines, and AML checks.

### Rules for Service Files

1. **All DB-mutating service functions must explicitly manage transactions.** If a function calls `pool.query()` without a preceding `BEGIN ISOLATION LEVEL SERIALIZABLE` (for money operations) or `BEGIN` (for non-money operations), flag it.

2. **Wallet lock acquisition pattern:** Any service function that modifies two wallets must acquire locks in ascending UUID order. Enforce this by sorting the wallet IDs before locking:
   ```typescript
   const [firstId, secondId] = [walletA.id, walletB.id].sort();
   ```

3. **Service functions must not import from route files.** Dependency direction is strictly: routes → services → repositories → DB. No circular imports.

4. **All monetary arithmetic must be typed as `bigint`.** If Claude generates a monetary calculation using `number`, it must immediately correct it.

5. **Compliance events:** Any function that makes an AML decision must insert a record into `compliance_events` table within the same transaction. This is not optional.

---

## File Glob: `src/frontend/**/*`

**Context:** Frontend code handles UI display only. No financial calculations happen here.

### Rules for Frontend Files

1. **No monetary calculations on the frontend.** The frontend receives amounts from the backend as `amount_cents: integer` and formats them using `Intl.NumberFormat` only.

2. **Correct display formatting:**
   ```typescript
   const formatCents = (cents: number): string =>
     new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' })
       .format(cents / 100);
   // Result: "$10.50"
   ```
   This is the only permitted way to display monetary amounts. Do not use `(cents / 100).toFixed(2)`.

3. **No card data handling in React components.** Any component collecting card information must use Stripe Elements (`@stripe/react-stripe-js`). No input field with `type="text"` or `type="number"` may collect a card number, CVV, or expiry.

4. **Idempotency keys:** Transfer form components must generate a UUID v4 idempotency key on mount using `crypto.randomUUID()` and store it in `useRef` (not `useState`) so it persists across re-renders but does not cause re-renders. This key must be sent with every submission of that form instance.

5. **Error message mapping:** Frontend must map backend error codes to user-facing messages. Never display raw error codes or backend error messages to the user:
   ```typescript
   const ERROR_MESSAGES: Record<string, string> = {
     'INSUFFICIENT_FUNDS': 'You don\'t have enough funds for this transfer.',
     'RECIPIENT_FROZEN': 'This recipient\'s account is temporarily unavailable.',
     'KYC_REQUIRED': 'Please complete identity verification to continue.',
     'DAILY_LIMIT_EXCEEDED': 'You\'ve reached your daily transfer limit.',
     'VELOCITY_LIMIT_EXCEEDED': 'Too many transfers. Please try again in an hour.',
   };
   ```

---

## File Glob: `tests/**/*`

**Context:** Test files verify correctness, security boundaries, and compliance behavior.

### Rules for Test Files

1. **No DB mocking for ledger tests.** Tests in `tests/integration/` that touch `ledger_entries`, `wallets`, or `transfers` must use a real PostgreSQL instance via `testcontainers` or a pre-seeded Docker DB. `jest.mock('pg')` is forbidden in integration tests.

2. **Concurrent transfer tests must use real parallelism.** Use `Promise.all()` to send concurrent requests. Simulated sequential concurrency is not acceptable for verifying serialization behavior.

3. **Test data amounts must use integer cents.** No test should use `amount: 10.5` — use `amount_cents: 1050`.

4. **Webhook tests must use real signature generation.** For Stripe webhook tests, generate the signature with `stripe.webhooks.generateTestHeaderString(payload, secret)`. Do not bypass signature verification in tests.

5. **Each edge case in the failure matrix must have a named test.** Use `describe` blocks matching the failure mode name from `specification.md`:
   ```typescript
   describe('Edge case: concurrent transfer requests', () => { ... });
   describe('Edge case: transfer to frozen recipient', () => { ... });
   ```

---

## Compliance-Sensitive File List

The following files require extra scrutiny. Before completing any edit to these files, Claude Code must confirm that no credentials, PAN data, or raw error messages are being introduced:

- `src/backend/services/TransferService.ts`
- `src/backend/services/LedgerService.ts`
- `src/backend/routes/payments/**/*`
- `src/backend/routes/kyc/**/*`
- `src/backend/db/migrations/**/*`
- `src/backend/config/secrets.ts`

---

## What NOT to Generate

- Any code that performs an `UPDATE` or `DELETE` on `ledger_entries`.
- Any migration that removes a `CHECK` constraint from a money column.
- Any `console.log` statement outside of test files.
- Any hardcoded credential, API key, or secret value (even as a placeholder in non-test files).
- Any `TODO`, `FIXME`, or `HACK` comment that relates to security or compliance — these must be resolved before commit, not deferred.
- Any `// @ts-ignore` or `// @ts-expect-error` suppressing type errors in money-path code.
