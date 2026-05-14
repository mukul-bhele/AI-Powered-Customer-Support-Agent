"""
Customers repository — all DB operations for the `customers` table.
One customer = one unique email address.
"""
from __future__ import annotations

from typing import Any

from customer_support_agent.repositories.sqlite.base import connect, row_to_dict


class CustomersRepository:

    def create_or_get(self, email: str, name: str | None = None) -> dict[str, Any]:
        """
        Return the existing customer for this email, or create a new one.
        Backfills the name if the existing row had it blank.
        """
        with connect() as conn:
            row = conn.execute("SELECT * FROM customers WHERE email = ?", (email,)).fetchone()

            if row:
                if name and not row["name"]:
                    conn.execute("UPDATE customers SET name = ? WHERE email = ?", (name, email))
                    row = conn.execute("SELECT * FROM customers WHERE email = ?", (email,)).fetchone()
                return row_to_dict(row) or {}

            conn.execute("INSERT INTO customers (email, name) VALUES (?, ?)", (email, name))
            created = conn.execute("SELECT * FROM customers WHERE email = ?", (email,)).fetchone()
            return row_to_dict(created) or {}

    def get_by_id(self, customer_id: int) -> dict[str, Any] | None:
        with connect() as conn:
            row = conn.execute("SELECT * FROM customers WHERE id = ?", (customer_id,)).fetchone()
            return row_to_dict(row)

    def get_by_email(self, email: str) -> dict[str, Any] | None:
        with connect() as conn:
            row = conn.execute("SELECT * FROM customers WHERE email = ?", (email,)).fetchone()
            return row_to_dict(row)
