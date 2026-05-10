const express = require('express');
const router = express.Router();

const { transactions } = require('../store');
const { createTransaction } = require('../models/transaction');
const { validateTransaction } = require('../validators/transactionValidator');
const { parseDate } = require('../utils/helpers');

// ---------------------------------------------------------------------------
// POST /transactions
// Creates a new transaction after validating every field.
// Returns the saved transaction with its auto-generated id and timestamp.
// ---------------------------------------------------------------------------
router.post('/', (req, res) => {
  const { valid, errors } = validateTransaction(req.body);

  if (!valid) {
    return res.status(400).json({
      error: 'Validation failed',
      details: errors,
    });
  }

  const transaction = createTransaction({
    fromAccount: req.body.fromAccount,
    toAccount: req.body.toAccount,
    amount: req.body.amount,
    currency: req.body.currency,
    type: req.body.type,
    // New transactions are immediately marked completed for simplicity.
    // In a real system you'd go through a pending → completed pipeline.
    status: 'completed',
  });

  transactions.push(transaction);

  return res.status(201).json(transaction);
});

// ---------------------------------------------------------------------------
// GET /transactions
// Returns all transactions, optionally narrowed by query parameters.
//
// Supported filters (all combinable, AND-logic):
//   ?accountId=ACC-12345   — transactions where this account sent or received
//   ?type=transfer         — deposit | withdrawal | transfer
//   ?from=2024-01-01       — transactions on or after this date (ISO 8601)
//   ?to=2024-01-31         — transactions on or before this date (ISO 8601)
// ---------------------------------------------------------------------------
router.get('/', (req, res) => {
  const { accountId, type, status, from, to } = req.query;

  let result = [...transactions];

  if (accountId) {
    result = result.filter(
      (t) => t.fromAccount === accountId || t.toAccount === accountId
    );
  }

  if (type) {
    result = result.filter((t) => t.type === type);
  }

  if (status) {
    const VALID_STATUSES = ['pending', 'completed', 'failed'];
    if (!VALID_STATUSES.includes(status)) {
      return res.status(400).json({
        error: `Invalid status "${status}". Must be one of: ${VALID_STATUSES.join(', ')}`,
      });
    }
    result = result.filter((t) => t.status === status);
  }

  if (from) {
    const fromDate = parseDate(from);
    if (!fromDate) {
      return res.status(400).json({ error: 'Invalid "from" date. Use ISO 8601 format, e.g. 2024-01-01' });
    }
    result = result.filter((t) => new Date(t.timestamp) >= fromDate);
  }

  if (to) {
    const toDate = parseDate(to);
    if (!toDate) {
      return res.status(400).json({ error: 'Invalid "to" date. Use ISO 8601 format, e.g. 2024-01-31' });
    }
    // Include the entire "to" day by moving the cutoff to the end of that day.
    toDate.setHours(23, 59, 59, 999);
    result = result.filter((t) => new Date(t.timestamp) <= toDate);
  }

  return res.status(200).json({
    count: result.length,
    transactions: result,
  });
});

// ---------------------------------------------------------------------------
// GET /transactions/export?format=csv
// Downloads all transactions (or a filtered subset) as a CSV file.
//
// Supports the same filters as GET /transactions:
//   ?accountId, ?type, ?from, ?to  — narrow down what gets exported
//   ?format=csv                     — only "csv" is supported for now
//
// IMPORTANT: this route must be registered before /:id so Express doesn't
// treat the literal string "export" as a transaction ID parameter.
// ---------------------------------------------------------------------------
router.get('/export', (req, res) => {
  const { format, accountId, type, from, to } = req.query;

  // Validate the format parameter before doing any work.
  if (!format) {
    return res.status(400).json({ error: 'Query parameter "format" is required. Currently supported: csv' });
  }
  if (format.toLowerCase() !== 'csv') {
    return res.status(400).json({ error: `Unsupported format "${format}". Currently supported: csv` });
  }

  // Apply the same filtering logic as GET /transactions.
  let result = [...transactions];

  if (accountId) {
    result = result.filter(
      (t) => t.fromAccount === accountId || t.toAccount === accountId
    );
  }

  if (type) {
    result = result.filter((t) => t.type === type);
  }

  if (from) {
    const fromDate = parseDate(from);
    if (!fromDate) {
      return res.status(400).json({ error: 'Invalid "from" date. Use ISO 8601 format, e.g. 2024-01-01' });
    }
    result = result.filter((t) => new Date(t.timestamp) >= fromDate);
  }

  if (to) {
    const toDate = parseDate(to);
    if (!toDate) {
      return res.status(400).json({ error: 'Invalid "to" date. Use ISO 8601 format, e.g. 2024-01-31' });
    }
    toDate.setHours(23, 59, 59, 999);
    result = result.filter((t) => new Date(t.timestamp) <= toDate);
  }

  // Build the CSV manually — no library needed for a flat, well-defined schema.
  // Values are wrapped in quotes and internal quotes are escaped (RFC 4180).
  const escape = (val) => `"${String(val).replace(/"/g, '""')}"`;

  const headers = ['id', 'fromAccount', 'toAccount', 'amount', 'currency', 'type', 'timestamp', 'status'];
  const rows = result.map((t) =>
    headers.map((h) => escape(t[h])).join(',')
  );

  const csv = [headers.join(','), ...rows].join('\r\n');

  res.setHeader('Content-Type', 'text/csv');
  res.setHeader('Content-Disposition', 'attachment; filename="transactions.csv"');
  return res.status(200).send(csv);
});

// ---------------------------------------------------------------------------
// GET /transactions/:id
// Looks up a single transaction by its UUID.
// Returns 404 with a clear message when nothing is found.
// ---------------------------------------------------------------------------
router.get('/:id', (req, res) => {
  const transaction = transactions.find((t) => t.id === req.params.id);

  if (!transaction) {
    return res.status(404).json({
      error: `Transaction with id "${req.params.id}" was not found`,
    });
  }

  return res.status(200).json(transaction);
});

module.exports = router;
