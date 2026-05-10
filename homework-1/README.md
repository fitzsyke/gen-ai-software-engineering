# 🏦 Homework 1: Banking Transactions API

> **Student Name**: Artem Saienko
> **Date Submitted**: 2026-05-10
> **AI Tools Used**: Claude Code (claude-sonnet-4-6)

---

## 📋 Project Overview

A lightweight RESTful API for banking transactions built with **Node.js** and **Express**.
All data lives in memory — no database required — making it easy to spin up and explore without any infrastructure setup.

**What's implemented:**
- ✅ Create transactions (deposits, withdrawals, transfers)
- ✅ List transactions with filters (account, type, date range)
- ✅ Retrieve a single transaction by ID
- ✅ Get current account balance (per currency)
- ✅ Get account activity summary (optional feature A)
- ✅ Simple interest calculation on current balance (optional feature B)
- ✅ Transaction export as CSV (optional feature C)
- ✅ Rate limiting — 100 requests per minute per IP (optional feature D)
- ✅ Input validation with detailed error messages

---

## 🏗️ Architecture

```
src/
├── index.js              ← Express app entry point & middleware setup
├── store.js              ← Shared in-memory transaction array (the "database")
├── models/
│   └── transaction.js    ← Transaction factory + allowed types & currencies
├── validators/
│   └── transactionValidator.js  ← Field-by-field validation logic
├── middleware/
│   └── rateLimiter.js    ← Fixed-window rate limiter (100 req/min per IP)
├── routes/
│   ├── transactions.js   ← POST /transactions, GET /transactions, GET /transactions/:id, GET /transactions/export
│   └── accounts.js       ← GET /accounts/:id/balance, GET /accounts/:id/summary, GET /accounts/:id/interest
└── utils/
    └── helpers.js        ← Shared pure functions (rounding, date parsing)
```

**Key design decisions:**
- `store.js` is a plain module-level array — any route file that requires it gets the same reference, so writes are immediately visible to reads.
- Validation runs on the raw request body before any business logic touches it, keeping routes clean.
- Balance calculation considers only `"completed"` transactions; `"pending"` and `"failed"` ones don't affect the settled amount.

---

## 🔌 API Endpoints

### `POST /transactions` — Create a transaction

**Request body:**
```json
{
  "fromAccount": "ACC-12345",
  "toAccount":   "ACC-67890",
  "amount":      100.50,
  "currency":    "USD",
  "type":        "transfer"
}
```

**Success response** `201 Created`:
```json
{
  "id":          "3f1a2b4c-...",
  "fromAccount": "ACC-12345",
  "toAccount":   "ACC-67890",
  "amount":      100.50,
  "currency":    "USD",
  "type":        "transfer",
  "timestamp":   "2026-05-10T12:00:00.000Z",
  "status":      "completed"
}
```

**Validation error** `400 Bad Request`:
```json
{
  "error": "Validation failed",
  "details": [
    { "field": "amount",   "message": "amount must be a positive number" },
    { "field": "currency", "message": "Invalid currency code \"XYZ\"..." }
  ]
}
```

---

### `GET /transactions` — List transactions

Optional query parameters:

| Parameter   | Description                             | Example                     |
|-------------|-----------------------------------------|-----------------------------|
| `accountId` | Filter by sender or receiver account    | `?accountId=ACC-12345`      |
| `type`      | Filter by transaction type              | `?type=transfer`            |
| `status`    | Filter by status                        | `?status=completed`         |
| `from`      | Include transactions on/after this date | `?from=2024-01-01`          |
| `to`        | Include transactions on/before this date| `?to=2024-01-31`            |

Filters can be combined: `?accountId=ACC-12345&type=transfer&from=2024-01-01`

**Success response** `200 OK`:
```json
{
  "count": 2,
  "transactions": [ ... ]
}
```

---

### `GET /transactions/:id` — Get a single transaction

**Success response** `200 OK` — the transaction object.
**Not found** `404 Not Found`:
```json
{ "error": "Transaction with id \"abc\" was not found" }
```

---

### `GET /accounts/:accountId/balance` — Get account balance

Returns the net settled balance for each currency the account has used.

**Success response** `200 OK`:
```json
{
  "accountId": "ACC-12345",
  "balances": {
    "USD": 350.00,
    "EUR": -50.00
  }
}
```

An empty `balances` object means the account has no completed transactions yet (not an error).

---

### `GET /transactions/export` — Export as CSV 📤

Downloads all transactions (or a filtered subset) as a `.csv` file.

Accepts the same filters as `GET /transactions` — combine them to export exactly the data you need.

**Query parameters:**

| Parameter   | Required | Description                                    | Example             |
|-------------|----------|------------------------------------------------|---------------------|
| `format`    | Yes      | Export format — only `csv` is supported        | `?format=csv`       |
| `accountId` | No       | Only include transactions for this account     | `&accountId=ACC-12345` |
| `type`      | No       | Filter by transaction type                     | `&type=transfer`    |
| `from`      | No       | Include transactions on/after this date        | `&from=2024-01-01`  |
| `to`        | No       | Include transactions on/before this date       | `&to=2024-01-31`    |

**Success response** `200 OK` — `Content-Type: text/csv`, `Content-Disposition: attachment; filename="transactions.csv"`:
```
id,fromAccount,toAccount,amount,currency,type,timestamp,status
"3f1a2b4c-...","ACC-12345","ACC-67890","100.5","USD","transfer","2026-05-10T12:00:00.000Z","completed"
```

**Validation errors** `400 Bad Request` — returned when `format` is missing or not `csv`.

---

### `GET /accounts/:accountId/interest` — Simple interest calculation 💰

Calculates how much interest the account would earn over a given number of days at a given annual rate, using the standard simple interest formula: **I = P × r × (days / 365)**.

**Query parameters:**

| Parameter | Required | Description                                     | Example  |
|-----------|----------|-------------------------------------------------|----------|
| `rate`    | Yes      | Annual interest rate as a decimal               | `0.05`   |
| `days`    | Yes      | Number of days the interest accrues over        | `30`     |

**Success response** `200 OK`:
```json
{
  "accountId":        "ACC-ALICE",
  "rate":             0.05,
  "days":             30,
  "balances":         { "USD": 2200.25 },
  "interest":         { "USD": 9.04 },
  "projectedBalance": { "USD": 2209.29 }
}
```

Calculated per currency. A negative balance produces negative interest (cost of debt).

**Validation errors** `400 Bad Request` — returned when `rate` or `days` are missing, non-numeric, or non-positive.

---

### `GET /accounts/:accountId/summary` — Get activity summary ⭐

A higher-level view: total money received, total sent, count, and most recent transaction date.

**Success response** `200 OK`:
```json
{
  "accountId":               "ACC-12345",
  "transactionCount":        5,
  "totalDeposits":           { "USD": 500.00, "EUR": 800.00 },
  "totalWithdrawals":        { "USD": 150.00 },
  "mostRecentTransactionAt": "2026-05-10T14:30:00.000Z"
}
```

Totals are grouped by currency — adding USD and EUR together would be meaningless.

---

## 🚦 Rate Limiting

Every endpoint is protected by a fixed-window rate limiter: **100 requests per minute per IP address**.

Every response includes these headers so clients can track their remaining quota:

| Header | Description |
|--------|-------------|
| `X-RateLimit-Limit` | Maximum requests allowed per window (always `100`) |
| `X-RateLimit-Remaining` | Requests still available in the current window |
| `X-RateLimit-Reset` | Unix timestamp (seconds) when the window resets |

When the limit is exceeded the API returns `429 Too Many Requests`:

```json
{
  "error": "Too many requests. You have exceeded the limit of 100 requests per minute.",
  "retryAfter": 42
}
```

With an additional header:
```
Retry-After: 42
```

The window resets automatically after 60 seconds — no action required by the caller.

---

## ✅ Validation Rules

| Field         | Rule                                                                      |
|---------------|---------------------------------------------------------------------------|
| `fromAccount` | Required · must match `ACC-[A-Z0-9]{5}` (e.g. `ACC-12345`, `ACC-AB1CD`) |
| `toAccount`   | Required · same format · must differ from `fromAccount`                   |
| `amount`      | Required · positive number · maximum 2 decimal places                    |
| `currency`    | Required · valid ISO 4217 code (USD, EUR, GBP, JPY, …)                   |
| `type`        | Required · one of `deposit`, `withdrawal`, `transfer`                    |

---

## 🛠️ Tech Stack

| Tool          | Purpose                             |
|---------------|-------------------------------------|
| Node.js ≥ 18  | Runtime                             |
| Express 4.x   | HTTP routing & middleware           |
| uuid 11.x     | Auto-generating unique transaction IDs |
| nodemon       | Dev-only auto-restart on file save  |

---

## 📖 Additional Guides

| Guide | Description |
|-------|-------------|
| [HOWTORUN.md](HOWTORUN.md) | Step-by-step instructions to install and start the server |
| [docs/vscode-preview-guide.md](docs/vscode-preview-guide.md) | How to launch and demo the API using the Claude Code VS Code Preview |
| [docs/github-issues.md](docs/github-issues.md) | GitHub issue descriptions for all implemented features |

---

## 📁 Full Project Structure

```
homework-1/
├── 📄 README.md
├── 📄 HOWTORUN.md
├── 📄 package.json
├── 📂 src/
│   ├── index.js
│   ├── store.js
│   ├── 📂 models/
│   │   └── transaction.js
│   ├── 📂 validators/
│   │   └── transactionValidator.js
│   ├── 📂 routes/
│   │   ├── transactions.js
│   │   └── accounts.js
│   └── 📂 utils/
│       └── helpers.js
├── 📂 docs/
│   ├── 1-ai-prompt.md
│   └── 📂 screenshots/
├── 📂 demo/
│   ├── run.sh
│   ├── sample-requests.http
│   └── sample-data.json
```

---

<div align="center">

*This project was completed as part of the AI-Assisted Development course.*

</div>
