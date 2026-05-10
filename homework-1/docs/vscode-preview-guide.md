# 🖥️ Running the API Demo in VS Code Preview

This guide walks you through launching and testing the Banking Transactions API
using the **Claude Code Preview** feature inside VS Code — no terminal juggling required.

---

## Prerequisites

| Requirement | Details |
|-------------|---------|
| **VS Code** | Any recent version |
| **Claude Code extension** | Installed and signed in |
| **Node.js ≥ 18** | [nodejs.org](https://nodejs.org) |
| **Dependencies installed** | Run `npm install` inside `homework-1/` once before starting |

---

## How It Works

Claude Code reads a file called `.claude/launch.json` at the repo root to know
which servers exist and how to start them.

> **Important:** The `.claude/` folder is listed in `.gitignore` — it is never
> committed to the repository. You must create it locally before using the preview.

### Setting up `.claude/launch.json`

A ready-made copy of the config is tracked in `demo/launch.json`. Copy it into place:

```bash
# Run this from the repo root (gen-ai-software-engineering/)
mkdir -p .claude
cp homework-1/demo/launch.json .claude/launch.json
```

The file contains two configurations for this project:

```json
{
  "version": "0.0.1",
  "configurations": [
    {
      "name": "homework-1 (production)",
      "runtimeExecutable": "npm",
      "runtimeArgs": ["start"],
      "port": 3000,
      "autoPort": true,
      "cwd": "homework-1"
    },
    {
      "name": "homework-1 (dev / nodemon)",
      "runtimeExecutable": "npm",
      "runtimeArgs": ["run", "dev"],
      "port": 3000,
      "autoPort": true,
      "cwd": "homework-1"
    }
  ]
}
```

`autoPort: true` means if port 3000 is already in use, Claude Code assigns the next free port automatically and tells you which one it chose.

---

## Step 1 — Start the Server

Open the Claude Code chat panel in VS Code and ask:

```
Start the homework-1 dev server
```

Claude Code reads `.claude/launch.json`, starts the server, and tells you which port it's running on (e.g. `http://localhost:3000`).

To start the production variant instead:

```
Start the homework-1 production server
```

---

## Step 2 — Open the Preview

Once the server is running, the Preview panel opens automatically (or you can ask):

```
Show me the API preview
```

Navigate to `http://localhost:<port>/` in the preview — you'll see the health-check response confirming all available endpoints.

---

## Step 3 — Run the Demo

Ask Claude Code to walk through the API. For example:

```
Demonstrate the API in the preview — create some transactions,
check balances, export as CSV, and trigger a validation error.
```

Claude Code will call each endpoint directly inside the preview and show you the responses.

You can also test endpoints manually in the preview address bar:

| What to test | URL |
|--------------|-----|
| Health check | `http://localhost:<port>/` |
| All transactions | `http://localhost:<port>/transactions` |
| Alice's transactions | `http://localhost:<port>/transactions?accountId=ACC-ALICE` |
| Filter by type | `http://localhost:<port>/transactions?type=transfer` |
| Account balance | `http://localhost:<port>/accounts/ACC-ALICE/balance` |
| Account summary | `http://localhost:<port>/accounts/ACC-ALICE/summary` |
| Interest (5%, 30 days) | `http://localhost:<port>/accounts/ACC-ALICE/interest?rate=0.05&days=30` |
| Export all as CSV | `http://localhost:<port>/transactions/export?format=csv` |
| Export Alice's CSV | `http://localhost:<port>/transactions/export?format=csv&accountId=ACC-ALICE` |

> Replace `<port>` with the actual port shown when the server started (default: `3000`).

---

## Step 4 — Create Transactions via the Preview

POST requests can't be made from the address bar directly. Ask Claude Code to seed data:

```
Seed some demo transactions in the preview — a deposit, a transfer, and a withdrawal
```

Or use the `demo/sample-requests.http` file with the
[REST Client extension](https://marketplace.visualstudio.com/items?itemName=humao.rest-client):

1. Open `homework-1/demo/sample-requests.http` in VS Code
2. Click **Send Request** above any `###` block
3. The response appears in a split panel on the right

---

## Step 5 — Test the CSV Export

1. Navigate to `http://localhost:<port>/transactions/export?format=csv` in the preview
2. The browser downloads `transactions.csv` automatically
3. Open it in VS Code or Excel to verify the contents

To export a filtered subset:
```
http://localhost:<port>/transactions/export?format=csv&accountId=ACC-ALICE&type=transfer
```

---

## Step 6 — Trigger Error Cases

These URLs demonstrate validation and error handling — useful for screenshots:

| Scenario | URL / Action |
|----------|-------------|
| Invalid account format | POST with `"fromAccount": "bad"` |
| Negative amount | POST with `"amount": -50` |
| Unknown currency | POST with `"currency": "XYZ"` |
| Transaction not found | `GET /transactions/00000000-0000-0000-0000-000000000000` |
| Unsupported export format | `GET /transactions/export?format=xml` |
| Rate limit (429) | Send 100+ rapid requests to any endpoint |

---

## Switching Between Dev and Production

| Mode | Behaviour |
|------|-----------|
| **dev (nodemon)** | Auto-restarts when you save a source file — ideal for active development |
| **production** | Plain `node` process — mirrors how the app runs in a real environment |

Both servers are stateless — restarting either one clears all in-memory transactions.

To switch, just ask Claude Code:

```
Stop the current server and start the production one instead
```

---

## Troubleshooting

**Server won't start**
- Make sure you ran `npm install` inside `homework-1/` first
- Check that Node.js ≥ 18 is installed: `node --version`

**Port already in use**
- `autoPort: true` in `launch.json` handles this automatically — Claude Code will pick the next free port and tell you which one it chose

**Preview shows a blank page**
- The API returns JSON, not HTML — the browser may show a blank page for binary/CSV responses. Use the address bar or REST Client for those endpoints.

**Rate limit hit during testing**
- The 100 req/min window resets automatically after 60 seconds
- Restart the server to clear the counter immediately
