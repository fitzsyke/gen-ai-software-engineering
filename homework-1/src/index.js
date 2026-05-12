const express = require('express');

const transactionRoutes = require('./routes/transactions');
const accountRoutes = require('./routes/accounts');
const rateLimiter = require('./middleware/rateLimiter');

const app = express();
const PORT = process.env.PORT || 3000;

// Parse incoming JSON request bodies.
app.use(express.json());

// Apply rate limiting to every endpoint: 100 requests per minute per IP.
app.use(rateLimiter);

// --- Routes ---
app.use('/transactions', transactionRoutes);
app.use('/accounts', accountRoutes);

// A friendly health-check root endpoint so you can quickly confirm the server is alive.
app.get('/', (req, res) => {
  res.json({
    name: 'Banking Transactions API',
    version: '1.0.0',
    status: 'running',
    endpoints: [
      'POST   /transactions',
      'GET    /transactions',
      'GET    /transactions/:id',
      'GET    /accounts/:accountId/balance',
      'GET    /accounts/:accountId/summary',
      'GET    /transactions/export?format=csv',
      'GET    /accounts/:accountId/interest?rate=0.05&days=30',
    ],
  });
});

// Catch-all for any route we don't recognise.
app.use((req, res) => {
  res.status(404).json({ error: `Route "${req.method} ${req.path}" not found` });
});

// Global error handler — catches anything that slips through a route handler.
// eslint-disable-next-line no-unused-vars
app.use((err, req, res, next) => {
  console.error('Unexpected error:', err);
  res.status(500).json({ error: 'An unexpected server error occurred' });
});

app.listen(PORT, () => {
  const url = `http://localhost:${PORT}`;
  console.log([
    '',
    '╔════════════════════════════════════════╗',
    '║   Banking Transactions API is running  ║',
    '╠════════════════════════════════════════╣',
    `║  Port    : ${PORT}${' '.repeat(28 - String(PORT).length)}║`,
    `║  Base URL: ${url}${' '.repeat(28 - url.length)}║`,
    '╠════════════════════════════════════════╣',
    '║  Endpoints                             ║',
    '║  POST   /transactions                  ║',
    '║  GET    /transactions                  ║',
    '║  GET    /transactions/:id              ║',
    '║  GET    /accounts/:id/balance          ║',
    '║  GET    /accounts/:id/summary          ║',
    '║  GET    /accounts/:id/interest         ║',
    '╚════════════════════════════════════════╝',
    '',
  ].join('\n'));
});

module.exports = app;
