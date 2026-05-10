const { v4: uuidv4 } = require('uuid');

// The three things a transaction can be.
// Deposits bring money into an account, withdrawals take it out,
// and transfers move it between two accounts.
const VALID_TYPES = ['deposit', 'withdrawal', 'transfer'];

// A curated subset of ISO 4217 currency codes.
// Covers all major world currencies — add more here if needed.
const VALID_CURRENCIES = new Set([
  'USD', 'EUR', 'GBP', 'JPY', 'AUD', 'CAD', 'CHF', 'CNY', 'SEK', 'NZD',
  'MXN', 'SGD', 'HKD', 'NOK', 'DKK', 'PLN', 'CZK', 'HUF', 'ILS', 'RUB',
  'INR', 'BRL', 'ZAR', 'TRY', 'KRW', 'THB', 'IDR', 'MYR', 'PHP', 'AED',
  'SAR', 'QAR', 'KWD', 'BHD', 'OMR', 'JOD', 'EGP', 'NGN', 'GHS', 'KES',
]);

/**
 * Builds a complete transaction object from user-supplied fields.
 * Auto-generates the id, timestamp, and initial status so callers
 * only need to provide the business data.
 */
function createTransaction({ fromAccount, toAccount, amount, currency, type, status = 'completed' }) {
  return {
    id: uuidv4(),
    fromAccount,
    toAccount,
    amount,
    currency: currency.toUpperCase(),
    type,
    timestamp: new Date().toISOString(),
    status,
  };
}

module.exports = { createTransaction, VALID_TYPES, VALID_CURRENCIES };
