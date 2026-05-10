# 📋 GitHub Issues — Banking Transactions API

Descriptions for all seven GitHub issues tracking the features of Homework 1.

---

## Issue 1 — Core API Implementation

**Title:** `Core API Implementation — transaction CRUD endpoints`
**Labels:** `homework-1`, `feature`

### Overview
Implement the foundational REST endpoints for the Banking Transactions API.

### Endpoints
- `POST /transactions` — create a new transaction
- `GET /transactions` — list all transactions
- `GET /transactions/:id` — retrieve a single transaction by ID
- `GET /accounts/:accountId/balance` — get the current balance for an account

### Transaction Model
```json
{
  "id": "string (auto-generated UUID)",
  "fromAccount": "string",
  "toAccount": "string",
  "amount": "number",
  "currency": "string (ISO 4217)",
  "type": "string (deposit | withdrawal | transfer)",
  "timestamp": "ISO 8601 datetime (auto-generated)",
  "status": "string (pending | completed | failed)"
}
```

### Acceptance Criteria
- [ ] All four endpoints respond with correct HTTP status codes (200, 201, 404)
- [ ] Transactions are stored in memory (no database required)
- [ ] Balance is calculated per currency from completed transactions
- [ ] Server returns JSON on all endpoints

---

## Issue 2 — Transaction Validation

**Title:** `Transaction Validation — amounts, account format, currency, type`
**Labels:** `homework-1`, `feature`

### Overview
Add input validation to `POST /transactions` so invalid requests are rejected
with a clear, structured error response before any data is stored.

### Validation Rules
| Field | Rule |
|-------|------|
| `fromAccount` | Required · must match `ACC-[A-Z0-9]{5}` |
| `toAccount` | Required · same format · must differ from `fromAccount` |
| `amount` | Required · positive number · max 2 decimal places |
| `currency` | Required · valid ISO 4217 code (USD, EUR, GBP, …) |
| `type` | Required · one of `deposit`, `withdrawal`, `transfer` |

### Error Response Format
Returns `400 Bad Request` with all validation failures at once:
```json
{
  "error": "Validation failed",
  "details": [
    { "field": "amount", "message": "amount must be a positive number" },
    { "field": "currency", "message": "Invalid currency code \"XYZ\"" }
  ]
}
```

### Acceptance Criteria
- [ ] All fields are validated before any storage write
- [ ] All errors are collected and returned together (not one at a time)
- [ ] Invalid account format returns a descriptive message
- [ ] Unsupported currency code returns a descriptive message

---

## Issue 3 — Transaction History Filtering

**Title:** `Transaction History — filter by account, type, and date range`
**Labels:** `homework-1`, `feature`

### Overview
Extend `GET /transactions` to support query-parameter filtering so callers
can retrieve a targeted subset of transactions.

### Supported Filters
| Parameter | Description | Example |
|-----------|-------------|---------|
| `accountId` | Transactions where this account sent or received | `?accountId=ACC-12345` |
| `type` | Transaction type | `?type=transfer` |
| `from` | On or after this date (ISO 8601) | `?from=2024-01-01` |
| `to` | On or before this date (ISO 8601) | `?to=2024-01-31` |

Filters are combinable: `?accountId=ACC-12345&type=transfer&from=2024-01-01`

### Response Format
```json
{
  "count": 2,
  "transactions": [ ... ]
}
```

### Acceptance Criteria
- [ ] Each filter works independently
- [ ] All filters can be combined (AND logic)
- [ ] Invalid date strings return `400` with a clear message
- [ ] Empty result set returns `{ "count": 0, "transactions": [] }` — not a 404

---

## Issue 4 — Transaction Summary Endpoint

**Title:** `Transaction Summary — account activity overview endpoint`
**Labels:** `homework-1`, `enhancement`

### Overview
Add a summary endpoint that gives a high-level view of an account's activity:
total money in, total money out, transaction count, and the most recent transaction date.

### Endpoint
`GET /accounts/:accountId/summary`

### Response
```json
{
  "accountId": "ACC-12345",
  "transactionCount": 5,
  "totalDeposits": 500.00,
  "totalWithdrawals": 150.00,
  "mostRecentTransactionAt": "2026-05-10T14:30:00.000Z"
}
```

An account with no transactions returns zero counts and `null` for the date — not an error.

### Acceptance Criteria
- [ ] Inflows (deposits received, transfers received) count toward `totalDeposits`
- [ ] Outflows (withdrawals sent, transfers sent) count toward `totalWithdrawals`
- [ ] Invalid account ID format returns `400`
- [ ] Account with no transactions returns a valid response with zero values

---

## Issue 5 — Simple Interest Calculation

**Title:** `Simple Interest Calculation — project earnings on current balance`
**Labels:** `homework-1`, `enhancement`

### Overview
Add an endpoint that calculates how much simple interest an account would earn
over a given number of days at a given annual rate.

### Endpoint
`GET /accounts/:accountId/interest?rate=0.05&days=30`

### Formula
**Interest = Principal × Rate × (Days / 365)**

Calculated per currency. A negative balance produces negative interest (cost of debt).

### Query Parameters
| Parameter | Required | Description |
|-----------|----------|-------------|
| `rate` | Yes | Annual interest rate as a decimal (e.g. `0.05` = 5%) |
| `days` | Yes | Number of days to accrue interest over |

### Response
```json
{
  "accountId": "ACC-12345",
  "rate": 0.05,
  "days": 30,
  "balances": { "USD": 2200.00 },
  "interest": { "USD": 9.04 },
  "projectedBalance": { "USD": 2209.04 }
}
```

### Acceptance Criteria
- [ ] `rate` must be a positive number — `400` otherwise
- [ ] `days` must be a positive integer — `400` otherwise
- [ ] Interest and projected balance are rounded to 2 decimal places
- [ ] Multi-currency accounts return results for each currency

---

## Issue 6 — Transaction Export as CSV

**Title:** `Transaction Export — download transactions as a CSV file`
**Labels:** `homework-1`, `enhancement`

### Overview
Add an export endpoint that downloads transactions as a `.csv` file.
Supports the same filters as `GET /transactions` so callers can export
exactly the data they need.

### Endpoint
`GET /transactions/export?format=csv`

### Query Parameters
| Parameter | Required | Description |
|-----------|----------|-------------|
| `format` | Yes | Export format — only `csv` supported |
| `accountId` | No | Filter by account |
| `type` | No | Filter by transaction type |
| `from` | No | Include transactions on/after this date |
| `to` | No | Include transactions on/before this date |

### Response
- `Content-Type: text/csv`
- `Content-Disposition: attachment; filename="transactions.csv"`

```
id,fromAccount,toAccount,amount,currency,type,timestamp,status
"abc-123","ACC-12345","ACC-67890","100.5","USD","transfer","2026-05-10T12:00:00.000Z","completed"
```

### Acceptance Criteria
- [ ] Missing `format` parameter returns `400`
- [ ] Unsupported format (e.g. `xml`) returns `400`
- [ ] All filters from `GET /transactions` work the same way here
- [ ] Values containing quotes or commas are properly escaped (RFC 4180)
- [ ] Route `/export` does not conflict with `/:id`

---

## Issue 7 — Rate Limiting

**Title:** `Rate Limiting — 100 requests per minute per IP`
**Labels:** `homework-1`, `enhancement`

### Overview
Protect all endpoints with a fixed-window in-memory rate limiter.
No external dependency (no Redis) — consistent with the project's in-memory storage approach.

### Behaviour
- **Limit:** 100 requests per minute per IP address
- **Window:** Fixed 60-second window, resets automatically
- **Scope:** Applied globally — covers every endpoint

### Response Headers (on every request)
| Header | Description |
|--------|-------------|
| `X-RateLimit-Limit` | Always `100` |
| `X-RateLimit-Remaining` | Requests left in the current window |
| `X-RateLimit-Reset` | Unix timestamp when the window resets |

### When Limit is Exceeded
Returns `429 Too Many Requests`:
```json
{
  "error": "Too many requests. You have exceeded the limit of 100 requests per minute.",
  "retryAfter": 42
}
```
With header: `Retry-After: 42`

### Acceptance Criteria
- [ ] Requests 1–100 succeed and show decrementing `X-RateLimit-Remaining`
- [ ] Request 101 returns `429` with `Retry-After` header
- [ ] Window resets after 60 seconds — requests succeed again
- [ ] Each IP address has its own independent counter
