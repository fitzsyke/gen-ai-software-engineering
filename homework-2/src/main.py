"""
main.py — Application entry point for the Customer Support Ticket API.

This file wires together the FastAPI application:
  - Creates the app instance with metadata for the OpenAPI docs
  - Registers middleware (CORS)
  - Adds a global exception handler so all errors return JSON (never HTML)
  - Mounts the tickets router
  - Exposes a /health endpoint for quick smoke tests

To run the server:
  uvicorn src.main:app --reload

Then open http://localhost:8000/docs to explore the interactive API docs.
See HOWTORUN.md for full setup instructions and cURL examples.
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .routers.tickets import router as tickets_router
from .storage.ticket_store import store

# ── App instance ───────────────────────────────────────────────────────────────

app = FastAPI(
    title="Customer Support Ticket Management API",
    description=(
        "Phase 1 — CRUD operations and bulk multi-format import "
        "for customer support tickets.\n\n"
        "**Supported import formats:** CSV · JSON · XML\n\n"
        "See [API_REFERENCE.md](docs/API_REFERENCE.md) for detailed endpoint docs."
    ),
    version="1.0.0",
    docs_url="/docs",     # Swagger UI
    redoc_url="/redoc",   # ReDoc alternative
    contact={
        "name": "Homework 2 — Backend Architect",
        "url":  "https://github.com/your-org/gen-ai-software-engineering",
    },
)

# ── Middleware ─────────────────────────────────────────────────────────────────

# CORS is open for demo purposes. In production, replace "*" with your
# frontend's origin(s) to prevent cross-origin abuse.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],    # Allow any origin (demo only)
    allow_credentials=True,
    allow_methods=["*"],    # Allow all HTTP methods
    allow_headers=["*"],    # Allow all headers
)

# ── Global exception handler ───────────────────────────────────────────────────

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Catch any unhandled exception and return a JSON error response.

    Without this handler, FastAPI would return an HTML 500 page for unexpected
    errors. JSON is far more useful for API clients.
    """
    return JSONResponse(
        status_code=500,
        content={
            "error":   "Internal server error",
            "detail":  str(exc),
            "path":    str(request.url),
        },
    )

# ── Routers ────────────────────────────────────────────────────────────────────

app.include_router(tickets_router)

# ── System endpoints ───────────────────────────────────────────────────────────

@app.get(
    "/health",
    tags=["system"],
    summary="Health check",
    response_description="Server status and current ticket count",
)
async def health() -> dict:
    """
    Quick health check endpoint.

    Returns the server status and current number of tickets in the store.
    Use this to confirm the server is running and the store is wired correctly.

    Example response:
    ```json
    {"status": "ok", "ticket_count": 42}
    ```
    """
    return {
        "status":       "ok",
        "ticket_count": store.count(),
        "version":      "1.0.0",
    }
