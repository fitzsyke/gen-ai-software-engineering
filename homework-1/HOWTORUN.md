# ▶️ How to Run the Banking Transactions API

---

## Prerequisites

- **Node.js** version 18 or higher — [download here](https://nodejs.org)
- **npm** (comes bundled with Node.js)

Verify you have the right version:
```bash
node --version   # should print v18.x.x or higher
npm --version    # should print 9.x.x or higher
```

---

## 1. Navigate to the homework-1 folder

```bash
cd homework-1
```

---

## 2. Install dependencies

```bash
npm install
```

This installs Express (the web framework) and uuid (for generating unique transaction IDs).
The `node_modules/` folder is created locally and is excluded from git.

---

## 3. Start the server

**For normal use:**
```bash
npm start
```

**For development (auto-restarts when you save a file):**
```bash
npm run dev
```

You should see:
```
╔════════════════════════════════════════╗
║   Banking Transactions API is running  ║
╠════════════════════════════════════════╣
║  Port    : 3000                        ║
║  Base URL: http://localhost:3000       ║
...
```

---

## 4. Try it out

Open a second terminal and run any of the following:

### Create a transfer
```bash
curl -s -X POST http://localhost:3000/transactions \
  -H "Content-Type: application/json" \
  -d '{
    "fromAccount": "ACC-12345",
    "toAccount":   "ACC-67890",
    "amount":      100.50,
    "currency":    "USD",
    "type":        "transfer"
  }' | jq
```

### List all transactions
```bash
curl -s http://localhost:3000/transactions | jq
```

### Filter by account
```bash
curl -s "http://localhost:3000/transactions?accountId=ACC-12345" | jq
```

### Filter by type and date range
```bash
curl -s "http://localhost:3000/transactions?type=transfer&from=2024-01-01&to=2024-12-31" | jq
```

### Get account balance
```bash
curl -s http://localhost:3000/accounts/ACC-12345/balance | jq
```

### Get account summary
```bash
curl -s http://localhost:3000/accounts/ACC-12345/summary | jq
```

> **Tip:** `jq` is a handy JSON formatter. If you don't have it, just remove `| jq` from the commands above — the output will still be correct, just less readable.

---

## 5. Use the demo script (optional)

The `demo/` folder contains ready-made files for a full walkthrough:

```bash
# Make the shell script executable (first time only)
chmod +x demo/run.sh

# Install and start the server in one step
./demo/run.sh
```

To test all endpoints at once, open `demo/sample-requests.http` in **VS Code** with the
[REST Client extension](https://marketplace.visualstudio.com/items?itemName=humao.rest-client)
and click **Send Request** above any `###` block.

---

## 6. Run in VS Code Preview with Claude Code (optional)

If you use the **Claude Code extension** in VS Code, you can start and demo the API
entirely inside the editor — no terminal or Postman needed.

See **[docs/vscode-preview-guide.md](docs/vscode-preview-guide.md)** for the full walkthrough,
including how to set up `.claude/launch.json` from the pre-made copy in `demo/`.

---

## 7. Change the port (optional)

The server defaults to port **3000**. To use a different port, set the `PORT` environment variable:

```bash
PORT=8080 npm start
```

---

## Stopping the server

Press `Ctrl + C` in the terminal where the server is running.

> **Note:** All data is stored in memory. Stopping the server clears everything — that's by design for this demo API.
