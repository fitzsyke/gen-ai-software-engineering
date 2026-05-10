// In-memory rate limiter: 100 requests per minute per IP address.
// Uses a sliding fixed-window strategy — the window resets 60 seconds
// after it first opened for that IP, not after each request.
//
// The Map grows by one entry per unique IP and is never persisted,
// so it resets automatically when the server restarts.

const LIMIT = 100;
const WINDOW_MS = 60 * 1000; // 1 minute in milliseconds

// { ip → { count: number, windowStart: number } }
const clients = new Map();

// Sweep out IPs whose window expired more than one cycle ago.
// Runs every minute so the Map doesn't grow forever on busy servers.
setInterval(() => {
  const cutoff = Date.now() - WINDOW_MS;
  for (const [ip, client] of clients) {
    if (client.windowStart < cutoff) clients.delete(ip);
  }
}, WINDOW_MS).unref(); // unref() so this timer doesn't prevent the process from exiting cleanly

function rateLimiter(req, res, next) {
  const ip = req.ip;
  const now = Date.now();

  const client = clients.get(ip);

  if (!client || now - client.windowStart >= WINDOW_MS) {
    // First request from this IP, or the previous window has expired — open a fresh one.
    clients.set(ip, { count: 1, windowStart: now });

    setRateLimitHeaders(res, LIMIT - 1, now);
    return next();
  }

  client.count += 1;

  const remaining = Math.max(0, LIMIT - client.count);
  const resetAt = client.windowStart + WINDOW_MS;

  setRateLimitHeaders(res, remaining, resetAt);

  if (client.count > LIMIT) {
    const retryAfter = Math.ceil((resetAt - now) / 1000);
    res.setHeader('Retry-After', retryAfter);

    return res.status(429).json({
      error: `Too many requests. You have exceeded the limit of ${LIMIT} requests per minute.`,
      retryAfter,
    });
  }

  return next();
}

/**
 * Attaches the three standard rate-limit headers to every response so callers
 * can see how much of their quota remains without waiting for a 429.
 */
function setRateLimitHeaders(res, remaining, resetAtMs) {
  res.setHeader('X-RateLimit-Limit', LIMIT);
  res.setHeader('X-RateLimit-Remaining', remaining);
  // X-RateLimit-Reset is conventionally a Unix timestamp in seconds.
  res.setHeader('X-RateLimit-Reset', Math.ceil(resetAtMs / 1000));
}

module.exports = rateLimiter;
