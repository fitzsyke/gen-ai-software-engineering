const { VALID_TYPES, VALID_CURRENCIES } = require('../models/transaction');
const { hasMoreThanTwoDecimals } = require('../utils/helpers');

// Account numbers must look like ACC- followed by exactly 5 uppercase letters or digits.
// Examples of valid accounts: ACC-12345, ACC-AB1CD
const ACCOUNT_PATTERN = /^ACC-[A-Z0-9]{5}$/;

/**
 * Validates the body of a POST /transactions request.
 *
 * Returns an object with:
 *   valid   — true when all fields pass, false otherwise
 *   errors  — array of { field, message } objects describing every problem found
 *
 * We collect all errors at once (rather than stopping at the first one)
 * so the caller gets a complete picture of what needs fixing.
 */
function validateTransaction(body) {
  const errors = [];

  // --- fromAccount ---
  if (!body.fromAccount) {
    errors.push({ field: 'fromAccount', message: 'fromAccount is required' });
  } else if (!ACCOUNT_PATTERN.test(body.fromAccount)) {
    errors.push({
      field: 'fromAccount',
      message: 'fromAccount must follow the format ACC-XXXXX (5 uppercase letters or digits)',
    });
  }

  // --- toAccount ---
  if (!body.toAccount) {
    errors.push({ field: 'toAccount', message: 'toAccount is required' });
  } else if (!ACCOUNT_PATTERN.test(body.toAccount)) {
    errors.push({
      field: 'toAccount',
      message: 'toAccount must follow the format ACC-XXXXX (5 uppercase letters or digits)',
    });
  }

  // Sending money to yourself doesn't make sense — catch it early.
  if (
    body.fromAccount &&
    body.toAccount &&
    ACCOUNT_PATTERN.test(body.fromAccount) &&
    ACCOUNT_PATTERN.test(body.toAccount) &&
    body.fromAccount === body.toAccount
  ) {
    errors.push({ field: 'toAccount', message: 'fromAccount and toAccount must be different' });
  }

  // --- amount ---
  if (body.amount === undefined || body.amount === null || body.amount === '') {
    errors.push({ field: 'amount', message: 'amount is required' });
  } else if (typeof body.amount !== 'number' || !isFinite(body.amount)) {
    errors.push({ field: 'amount', message: 'amount must be a number' });
  } else if (body.amount <= 0) {
    errors.push({ field: 'amount', message: 'amount must be a positive number' });
  } else if (hasMoreThanTwoDecimals(body.amount)) {
    errors.push({ field: 'amount', message: 'amount must have at most 2 decimal places' });
  }

  // --- currency ---
  if (!body.currency) {
    errors.push({ field: 'currency', message: 'currency is required' });
  } else if (!VALID_CURRENCIES.has(body.currency.toUpperCase())) {
    errors.push({
      field: 'currency',
      message: `Invalid currency code "${body.currency}". Use a standard ISO 4217 code such as USD, EUR, or GBP`,
    });
  }

  // --- type ---
  if (!body.type) {
    errors.push({ field: 'type', message: 'type is required' });
  } else if (!VALID_TYPES.includes(body.type)) {
    errors.push({
      field: 'type',
      message: `type must be one of: ${VALID_TYPES.join(', ')}`,
    });
  }

  return { valid: errors.length === 0, errors };
}

module.exports = { validateTransaction };
