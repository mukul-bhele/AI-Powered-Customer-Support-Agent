"""
Database foundation module.

Provides:
  - connect()    → opens a SQLite connection with sane defaults
  - row_to_dict  → converts a sqlite3.Row to a plain dict
  - init_db()    → creates all tables and triggers on first run
"""
from __future__ import annotations

import sqlite3
from typing import Any

from customer_support_agent.core.settings import ensure_directories, get_settings


def connect() -> sqlite3.Connection:
    """
    Open and return a SQLite connection to the application database.

    Settings are read from .env (see core/settings.py).
    - check_same_thread=False  → allows the same connection across FastAPI threads
    - row_factory=sqlite3.Row  → lets us access columns by name (row["email"])
    - PRAGMA foreign_keys=ON   → enforces FK constraints (e.g. ticket → customer)
    """
    settings = get_settings()
    ensure_directories(settings)

    conn = sqlite3.connect(str(settings.db_file), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    """Convert a sqlite3.Row to a plain dict, or return None if the row is None."""
    if row is None:
        return None
    return dict(row)
    
def init_db() -> None:
    """
    Create the database schema on application startup.

    Tables:
      customers  → one row per unique email address
      tickets    → support requests submitted by customers
      drafts     → AI-generated reply drafts for each ticket

    The trigger keeps tickets.updated_at in sync automatically
    whenever a ticket row is updated.
    """

    with connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS customers (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                email      TEXT UNIQUE NOT NULL,
                name       TEXT,
                company    TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS tickets (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id INTEGER REFERENCES customers(id),
                subject     TEXT NOT NULL,
                description TEXT NOT NULL,
                status      TEXT DEFAULT 'open',
                priority    TEXT DEFAULT 'medium',
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS drafts (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id    INTEGER REFERENCES tickets(id),
                content      TEXT NOT NULL,
                context_used TEXT,          -- JSON blob: memory/KB/tool signals
                status       TEXT DEFAULT 'pending',
                created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            -- Automatically update tickets.updated_at on every UPDATE
            CREATE TRIGGER IF NOT EXISTS tickets_updated_at_trigger
            AFTER UPDATE ON tickets
            FOR EACH ROW
            BEGIN
                UPDATE tickets SET updated_at = CURRENT_TIMESTAMP WHERE id = OLD.id;
            END;
            """
        )
