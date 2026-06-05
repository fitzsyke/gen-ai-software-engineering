"""
conftest.py — Shared pytest fixtures for the ticket management test suite.

Provides:
  - client        : FastAPI TestClient (synchronous, wraps the real app)
  - reset_store   : autouse fixture that clears the in-memory store before each test
  - sample_ticket : A valid TicketCreate payload dict (reusable across test files)
  - created_ticket: Helper that POSTs a ticket and returns the response JSON

Run from the homework-2/ directory:
  pytest tests/ --cov=src --cov-report=term-missing
"""

import pytest
from starlette.testclient import TestClient

from src.main import app
from src.storage.ticket_store import store


# ── Store isolation ────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def reset_store():
    """
    Clear the in-memory store before (and after) every test.

    autouse=True means this runs automatically for every test in the suite
    without needing to declare it as a parameter.
    """
    store.clear()
    yield
    store.clear()


# ── HTTP test client ───────────────────────────────────────────────────────────


@pytest.fixture
def client() -> TestClient:
    """
    Return a synchronous FastAPI TestClient.

    Uses the real app instance — routers, services, storage — so these are
    true integration tests at the HTTP layer. The in-memory store is isolated
    per-test by the reset_store fixture above.
    """
    return TestClient(app)


# ── Reusable payload builders ──────────────────────────────────────────────────


@pytest.fixture
def sample_ticket() -> dict:
    """
    A minimal valid TicketCreate payload as a plain dict.

    Copy and mutate in individual tests to create edge-case variants:
        data = sample_ticket.copy()
        data["priority"] = "low"
    """
    return {
        "customer_id":    "cust-001",
        "customer_email": "alice@example.com",
        "customer_name":  "Alice Johnson",
        "subject":        "Cannot log into my account",
        "description":    "I have been unable to access my account since yesterday evening.",
        "category":       "account_access",
        "priority":       "urgent",
    }


@pytest.fixture
def created_ticket(client: TestClient, sample_ticket: dict) -> dict:
    """
    Create one ticket via the API and return its JSON response body.

    Use when a test needs an existing ticket to operate on (GET, PUT, DELETE).
    """
    response = client.post("/tickets", json=sample_ticket)
    assert response.status_code == 201
    return response.json()
