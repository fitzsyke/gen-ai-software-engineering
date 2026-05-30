"""
ticket_store.py — Thread-safe in-memory storage for tickets.

Why in-memory?
  Phase 1 keeps the setup frictionless — no database to install or configure.
  A single 'pip install + uvicorn' is all you need to run the system.

  Trade-off: tickets are lost when the server restarts.
  Phase 2 will swap this layer for a persistent store without touching
  the service layer (that's the benefit of the layered architecture).

Thread safety:
  FastAPI can serve requests concurrently. All write operations (add, update,
  delete) acquire a threading.Lock so concurrent requests never corrupt the dict.
  Read operations return a list snapshot, not a reference to the internal dict.

Usage:
  Import the module-level singleton from anywhere in the app:

    from src.storage.ticket_store import store
    ticket = store.get("some-uuid")
"""

import threading
from typing import Dict, List, Optional

from ..models.ticket import Ticket


class TicketStore:
    """
    In-memory key/value store for Ticket objects.

    Keys   : ticket id as a plain string (UUID stringified)
    Values : Ticket Pydantic model instances

    All methods that modify state are protected by a threading.Lock.
    Read methods (get, all, count) are safe without locking because:
      - get() reads a single key (atomic in CPython)
      - all() takes a snapshot copy under the lock
      - count() reads len() which is atomic in CPython
    """

    def __init__(self) -> None:
        self._store: Dict[str, Ticket] = {}
        self._lock  = threading.Lock()

    # ── Write operations (lock-protected) ─────────────────────────────────────

    def add(self, ticket: Ticket) -> Ticket:
        """
        Persist a new ticket. Returns the same ticket for chaining.

        Raises ValueError if a ticket with that id already exists
        (prevents accidental overwrites — use update() instead).
        """
        with self._lock:
            ticket_id = str(ticket.id)
            if ticket_id in self._store:
                raise ValueError(f"Ticket '{ticket_id}' already exists")
            self._store[ticket_id] = ticket
        return ticket

    def update(self, ticket_id: str, updated_ticket: Ticket) -> Optional[Ticket]:
        """
        Replace an existing ticket with an updated version.

        Returns the updated ticket on success, or None if not found.
        """
        with self._lock:
            if ticket_id not in self._store:
                return None
            self._store[ticket_id] = updated_ticket
        return updated_ticket

    def delete(self, ticket_id: str) -> bool:
        """
        Remove a ticket by id.

        Returns True if the ticket was found and deleted, False if not found.
        """
        with self._lock:
            if ticket_id not in self._store:
                return False
            del self._store[ticket_id]
        return True

    # ── Read operations ────────────────────────────────────────────────────────

    def get(self, ticket_id: str) -> Optional[Ticket]:
        """Return the ticket with the given id, or None if not found."""
        return self._store.get(ticket_id)

    def all(self) -> List[Ticket]:
        """
        Return a snapshot of all tickets as a list.

        Takes the lock to avoid reading a partially-modified dict during a
        concurrent write. Returns a copy so callers can safely filter/sort it.
        """
        with self._lock:
            return list(self._store.values())

    def count(self) -> int:
        """Return the number of tickets currently in the store."""
        return len(self._store)

    def clear(self) -> None:
        """
        Remove all tickets from the store.

        Used exclusively in tests to reset state between test cases.
        Do not call in production code.
        """
        with self._lock:
            self._store.clear()


# ── Module-level singleton ─────────────────────────────────────────────────────
# Import this object everywhere instead of instantiating TicketStore directly.
# This ensures all parts of the app share exactly one store instance.
#
#   from src.storage.ticket_store import store

store = TicketStore()
