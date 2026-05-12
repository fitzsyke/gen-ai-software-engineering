/**
 * Rounds a number to exactly 2 decimal places.
 * Used when accumulating balances to avoid floating-point drift
 * (e.g. 0.1 + 0.2 producing 0.30000000000000004).
 */
function roundToTwo(num) {
  return Math.round((num + Number.EPSILON) * 100) / 100;
}

/**
 * Parses a date string and returns a Date object, or null if the
 * string isn't a valid date. Accepts any format JS Date can parse,
 * but ISO 8601 strings (e.g. "2024-01-15") work best.
 */
function parseDate(str) {
  if (!str) return null;
  const d = new Date(str);
  return isNaN(d.getTime()) ? null : d;
}

/**
 * Checks whether a number has more than 2 decimal places.
 * We use string conversion rather than multiplication to avoid
 * floating-point representation surprises.
 */
function hasMoreThanTwoDecimals(num) {
  const str = num.toString();
  const dotIndex = str.indexOf('.');
  if (dotIndex === -1) return false;
  return str.length - dotIndex - 1 > 2;
}

module.exports = { roundToTwo, parseDate, hasMoreThanTwoDecimals };
