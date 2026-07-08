# Research Notes — context7 Queries (Agent 2 / Code Generation)

## Query 1: Decimal arithmetic for monetary values
- Search: "decimal module quantize ROUND_HALF_UP for currency amounts and comparing Decimal instances"
- context7 library ID: `/python/cpython`
- Applied: Confirmed `Decimal(str(amount))` (constructing from the original JSON string, never via `float`) is the correct pattern for exact monetary arithmetic, and that `Decimal` supports direct comparison operators (`<`, `>`, `==`) without a separate `compare()` call for simple sign/threshold checks. Used in `pipeline/validator.py`'s `validate_transaction()` (parsing `amount` and checking the refund/negative-sign rule) and `pipeline/fraud_detector.py`'s `score_transaction()` (comparing `abs(amount)` against `HIGH_VALUE_THRESHOLD`).

## Query 2: Flask JSON API routes and template rendering
- Search: "JSON API route returning jsonify response and rendering a simple HTML template with data"
- context7 library ID: `/pallets/flask`
- Applied: Confirmed that a Flask view can return a plain `dict`/`list` directly for simple JSON endpoints (used for `/api/results` and `/api/summary` in `frontend/app.py`, via `jsonify()` for explicit content-type control), and that `render_template()` looks up templates in a `templates/` folder relative to the app module — used for the `/` dashboard route rendering `frontend/templates/dashboard.html` with `results` and `summary` passed as template variables.
