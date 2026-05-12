const express = require('express');
const router = express.Router();

const { transactions } = require('../store');
const { roundToTwo } = require('../utils/helpers');

// Re-use the same pattern that the validator checks for consistency.
const ACCOUNT_PATTERN = /^ACC-[A-Z0-9]{5}$/;

/**
 * Validates an accountId from the URL and sends a 400 response if it's wrong.
 * Returns true when the caller should stop (response already sent), false when all is fine.
 */
function rejectInvalidAccount(accountId, res) {
  if (!ACCOUNT_PATTERN.test(accountId)) {
    res.status(400).json({
      error: `"${accountId}" is not a valid account ID. Expected format: ACC-XXXXX (5 uppercase letters or digits)`,
    });
    return true;
  }
  return false;
}

/**
 * Works out how each transaction affects the given account's balance.
 * Returns a map of { currency → net amount } considering only completed transactions.
 *
 * Accounting rules:
 *   deposit   — toAccount receives money   (+)
 *   withdrawal — fromAccount loses money   (-)
 *   transfer  — fromAccount sends (-)  /  toAccount receives (+)
 */
function computeBalances(accountId) {
  const balances = {};

  for (const t of transactions) {
    // Pending or failed transactions don't count toward the settled balance.
    if (t.status !== 'completed') continue;

    const cur = t.currency;
    if (!(cur in balances)) balances[cur] = 0;

    const isFrom = t.fromAccount === accountId;
    const isTo = t.toAccount === accountId;

    if (t.type === 'deposit' && isTo) {
      balances[cur] += t.amount;
    } else if (t.type === 'withdrawal' && isFrom) {
      balances[cur] -= t.amount;
    } else if (t.type === 'transfer') {
      if (isFrom) balances[cur] -= t.amount;
      if (isTo) balances[cur] += t.amount;
    }
  }

  // Round every currency to 2 decimals so the response is always clean.
  for (const cur of Object.keys(balances)) {
    balances[cur] = roundToTwo(balances[cur]);
  }

  return balances;
}

// ---------------------------------------------------------------------------
// GET /accounts/:accountId/balance
// Returns the current settled balance for each currency the account has
// ever transacted in. An account with no transactions returns an empty
// balances object — not an error.
// ---------------------------------------------------------------------------
router.get('/:accountId/balance', (req, res) => {
  const { accountId } = req.params;
  if (rejectInvalidAccount(accountId, res)) return;

  const balances = computeBalances(accountId);

  return res.status(200).json({ accountId, balances });
});

// ---------------------------------------------------------------------------
// GET /accounts/:accountId/summary
// A higher-level view of account activity: total money in, total money out,
// how many transactions, and when the last one happened.
//
// Amounts are reported in the account's primary currency (the one used most).
// If the account operates in multiple currencies, each is summarised separately.
// ---------------------------------------------------------------------------
router.get('/:accountId/summary', (req, res) => {
  const { accountId } = req.params;
  if (rejectInvalidAccount(accountId, res)) return;

  const related = transactions.filter(
    (t) => t.fromAccount === accountId || t.toAccount === accountId
  );

  if (related.length === 0) {
    return res.status(200).json({
      accountId,
      transactionCount: 0,
      totalDeposits: {},
      totalWithdrawals: {},
      mostRecentTransactionAt: null,
    });
  }

  // Totals are tracked per currency — mixing USD and EUR into a single
  // number would be meaningless, so we mirror the structure of /balance.
  const totalDeposits = {};
  const totalWithdrawals = {};
  let mostRecent = null;

  for (const t of related) {
    const ts = new Date(t.timestamp);
    if (!mostRecent || ts > mostRecent) mostRecent = ts;

    const cur = t.currency;
    if (!(cur in totalDeposits)) { totalDeposits[cur] = 0; totalWithdrawals[cur] = 0; }

    const isFrom = t.fromAccount === accountId;
    const isTo   = t.toAccount   === accountId;

    if ((t.type === 'deposit' && isTo) || (t.type === 'transfer' && isTo)) {
      totalDeposits[cur] += t.amount;
    }
    if ((t.type === 'withdrawal' && isFrom) || (t.type === 'transfer' && isFrom)) {
      totalWithdrawals[cur] += t.amount;
    }
  }

  for (const cur of Object.keys(totalDeposits)) {
    totalDeposits[cur]   = roundToTwo(totalDeposits[cur]);
    totalWithdrawals[cur] = roundToTwo(totalWithdrawals[cur]);
  }

  return res.status(200).json({
    accountId,
    transactionCount: related.length,
    totalDeposits,
    totalWithdrawals,
    mostRecentTransactionAt: mostRecent ? mostRecent.toISOString() : null,
  });
});

// ---------------------------------------------------------------------------
// GET /accounts/:accountId/interest?rate=0.05&days=30
// Calculates simple interest earned on the current settled balance.
//
// Formula: Interest = Principal × Rate × (Days / 365)
//   - rate  — annual interest rate as a decimal (e.g. 0.05 = 5 % p.a.)
//   - days  — number of days the interest accrues over
//
// Interest is calculated per currency. Currencies with a negative balance
// (i.e. the account owes money) produce negative interest — that's the cost
// of the debt, which is mathematically consistent.
// ---------------------------------------------------------------------------
router.get('/:accountId/interest', (req, res) => {
  const { accountId } = req.params;
  if (rejectInvalidAccount(accountId, res)) return;

  const { rate, days } = req.query;

  // Validate rate — must be a finite positive number.
  const rateNum = parseFloat(rate);
  if (rate === undefined || rate === '') {
    return res.status(400).json({ error: 'Query parameter "rate" is required (e.g. ?rate=0.05 for 5% per year)' });
  }
  if (isNaN(rateNum) || !isFinite(rateNum) || rateNum <= 0) {
    return res.status(400).json({ error: '"rate" must be a positive number (e.g. 0.05 for 5% per year)' });
  }

  // Validate days — must be a positive integer.
  const daysNum = parseInt(days, 10);
  if (days === undefined || days === '') {
    return res.status(400).json({ error: 'Query parameter "days" is required (e.g. ?days=30)' });
  }
  if (isNaN(daysNum) || daysNum <= 0 || !Number.isInteger(daysNum)) {
    return res.status(400).json({ error: '"days" must be a positive whole number (e.g. 30)' });
  }

  const balances = computeBalances(accountId);

  // Interest = P × r × t   where t = days / 365 (simple interest, no compounding)
  const interest = {};
  const projectedBalance = {};
  const timeFraction = daysNum / 365;

  for (const [currency, principal] of Object.entries(balances)) {
    const earned = roundToTwo(principal * rateNum * timeFraction);
    interest[currency] = earned;
    projectedBalance[currency] = roundToTwo(principal + earned);
  }

  return res.status(200).json({
    accountId,
    rate: rateNum,
    days: daysNum,
    balances,
    interest,
    projectedBalance,
  });
});

module.exports = router;
