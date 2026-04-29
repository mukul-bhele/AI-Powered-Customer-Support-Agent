"""
Customers repository.

All database operations for the `customers` table.
One customer = one unique email address.
"""
from __future__ import annotations
from typing import Any
from customer_support_agent.repositories.sqlite.base import connect, row_to_dict


class CustomersRepository:
    def create_or_get(
        self,
        email: str,
        name: str | None = None,
        company: str | None = None,
    ) -> dict[str, Any]:
        """
        Return the existing customer for this email, or create a new one.
        If the customer already exists but is missing name/company,
        fill in those fields from the provided values.
        """
        with connect() as conn:
            row = conn.execute(
                "SELECT * FROM customers WHERE email = ?", (email,)
            ).fetchone()

            if row:
                # Customer exists — update any missing fields
                updates: list[str] = []
                values: list[Any] = []
                if name and not row["name"]:
                    updates.append("name = ?")
                    values.append(name)
                if company and not row["company"]:
                    updates.append("company = ?")
                    values.append(company)
               
                if updates:
                    values.append(email)
                    conn.execute(
                        f"UPDATE customers SET {', '.join(updates)} WHERE email = ?",
                        values,
                    )
                # Re-fetch so the returned dict has the latest values
                refreshed = conn.execute(
                    "SELECT * FROM customers WHERE email = ?", (email,)
                ).fetchone()
                return row_to_dict(refreshed) or {}

            # New customer — insert and return
            conn.execute(
                "INSERT INTO customers (email, name, company) VALUES (?, ?, ?)",
                (email, name, company),
            )
            created = conn.execute(
                "SELECT * FROM customers WHERE email = ?", (email,)
            ).fetchone()
            return row_to_dict(created) or {}

    def get_by_id(self, customer_id: int) -> dict[str, Any] | None:
        """Look up a customer by their primary key."""
        with connect() as conn:
            row = conn.execute(
                "SELECT * FROM customers WHERE id = ?", (customer_id,)
            ).fetchone()
            return row_to_dict(row)
  
    def get_by_email(self, email: str) -> dict[str, Any] | None:
        """Look up a customer by their email address."""
        with connect() as conn:
            row = conn.execute(
                "SELECT * FROM customers WHERE email = ?", (email,)
            ).fetchone()
            return row_to_dict(row)
