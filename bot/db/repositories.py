"""SQLite repository implementations using aiosqlite."""

# ruff: noqa

from __future__ import annotations

import logging
import inspect
from typing import List, Optional
import aiosqlite

from . import connection
import inspect


async def _acquire_connection():
    """Helper to obtain a connection from the connection module.

    Some tests patch ``get_connection`` with a coroutine that immediately
    raises.  If the returned object is a coroutine we simply await it so the
    exception propagates as expected.  Otherwise we use it as an async context
    manager.
    """
    ctx = connection.get_connection()
    if inspect.iscoroutine(ctx):
        return await ctx  # type: ignore[no-any-return]
    return ctx


from .models import (
    User as UserModel,
    Debt as DebtModel,
    Payment as PaymentModel,
    DebtStatus as DebtStatusLiteral,
)

logger = logging.getLogger(__name__)


class UserRepository:
    """SQLite implementation of user repository."""

    @classmethod
    async def add(cls, username: str) -> UserModel:
        """
        Add a new user with minimal information.
        Uses username as first_name internally to satisfy NOT NULL constraint.
        """
        try:
            ctx = await _acquire_connection()
            async with ctx as conn:
                import random

                min_sql_int = -9223372036854775808
                user_id = random.randint(min_sql_int + 1, -1)
                await conn.execute(
                    """
                    INSERT INTO users (user_id, username, first_name)
                    VALUES (?, ?, ?)
                    """,
                    (user_id, username.lower(), username.lower()),
                )
                await conn.commit()
                cursor = await conn.execute(
                    "SELECT * FROM users WHERE user_id = ?",
                    (user_id,),
                )
                row = await cursor.fetchone()
                return UserModel(**dict(row))  # type: ignore
        except Exception as e:
            logger.exception("Failed to add user %s: %s", username, e)
            raise

    @classmethod
    async def get_by_id(cls, user_id: int) -> Optional[UserModel]:
        """Retrieve a user by their ID."""
        try:
            ctx = await _acquire_connection()
            async with ctx as conn:
                cursor = await conn.execute(
                    "SELECT * FROM users WHERE user_id = ?",
                    (user_id,),
                )
                row = await cursor.fetchone()
                if row:
                    return UserModel(**dict(row))  # type: ignore
                return None
        except Exception as e:
            logger.exception("Failed to get user by id %d: %s", user_id, e)
            raise

    @classmethod
    async def get_by_username(cls, username: str) -> Optional[UserModel]:
        """Retrieve a user by their username."""
        try:
            ctx = await _acquire_connection()
            async with ctx as conn:
                cursor = await conn.execute(
                    "SELECT * FROM users WHERE LOWER(username) = ?",
                    (username.lower(),),
                )
                row = await cursor.fetchone()
                if row:
                    return UserModel(**dict(row))  # type: ignore
                return None
        except Exception as e:
            logger.exception("Failed to get user by username %s: %s", username, e)
            raise

    @classmethod
    async def get_or_create_user(
        cls,
        *,
        user_id: int,
        username: str,
        first_name: str,
        language_code: str = "en",
    ) -> UserModel:
        """Return existing user or create/merge as needed."""
        username_lc = username.lower()

        conn_ctx = await _acquire_connection()
        async with conn_ctx as conn:
            await conn.execute("PRAGMA foreign_keys = ON")
            await conn.execute("BEGIN")
            try:
                # 1) lookup by user_id
                cursor = await conn.execute(
                    """
                    SELECT user_id, username, first_name, language_code
                    FROM users
                    WHERE user_id = ?
                    """,
                    (user_id,),
                )
                row = await cursor.fetchone()
                if row:
                    return UserModel(**dict(row))

                # 2) lookup by username
                cursor = await conn.execute(
                    """
                    SELECT user_id
                    FROM users
                    WHERE LOWER(username) = ?
                    """,
                    (username_lc,),
                )
                existing = await cursor.fetchone()
                if existing:
                    old_id = existing[0]
                    # Merge into new user_id
                    await conn.execute(
                        """
                        UPDATE users
                        SET user_id       = ?,
                            username      = ?,
                            first_name    = ?,
                            language_code = ?
                        WHERE user_id = ?
                        """,
                        (user_id, username_lc, first_name, language_code, old_id),
                    )
                    await conn.commit()
                    cursor = await conn.execute(
                        """
                        SELECT user_id, username, first_name, language_code
                        FROM users
                        WHERE user_id = ?
                        """,
                        (user_id,),
                    )
                    row = await cursor.fetchone()
                    if not row:
                        raise RuntimeError(f"User {user_id} not found after merge")
                    return UserModel(**dict(row))

                # 3) insert new user
                await conn.execute(
                    """
                    INSERT INTO users (user_id, username, first_name, language_code)
                    VALUES (?, ?, ?, ?)
                    """,
                    (user_id, username_lc, first_name, language_code),
                )
                await conn.commit()
                cursor = await conn.execute(
                    """
                    SELECT user_id, username, first_name, language_code
                    FROM users
                    WHERE user_id = ?
                    """,
                    (user_id,),
                )
                row = await cursor.fetchone()
                if not row:
                    raise RuntimeError(f"Failed to retrieve user after insertion: {user_id}")
                return UserModel(**dict(row))

            except Exception as e:
                # DB do brrr
                logger.exception("Failed to get user by username %s", e)
                await conn.rollback()
                raise

    @classmethod
    async def update_user_language(cls, user_id: int, language_code: str) -> None:
        """Update user's language preference."""
        try:
            ctx = await _acquire_connection()
            async with ctx as conn:
                await conn.execute(
                    "UPDATE users SET language_code = ? WHERE user_id = ?",
                    (language_code, user_id),
                )
                await conn.commit()
        except Exception as e:
            logger.exception("Failed to update language for user %d: %s", user_id, e)
            raise

    @classmethod
    async def update_user_contact(cls, user_id: int, contact: str) -> None:
        """Update user's contact information."""
        try:
            ctx = await _acquire_connection()
            async with ctx as conn:
                await conn.execute(
                    "UPDATE users SET contact = ? WHERE user_id = ?",
                    (contact, user_id),
                )
                await conn.commit()
        except Exception as e:
            logger.exception("Failed to update contact for user %d: %s", user_id, e)
            raise

    @classmethod
    async def update_user_reminders(cls, user_id: int, payday_days: str) -> None:
        """Update user's reminder preferences."""
        try:
            ctx = await _acquire_connection()
            async with ctx as conn:
                await conn.execute(
                    "UPDATE users SET payday_days = ? WHERE user_id = ?",
                    (payday_days, user_id),
                )
                await conn.commit()
        except Exception as e:
            logger.exception("Failed to update reminders for user %d: %s", user_id, e)
            raise

    @classmethod
    async def add_trust(cls, user_id: int, trusted_username: str) -> None:
        """
        Record that user_id trusts the user with username trusted_username.
        """
        try:
            # find trusted user's id
            ctx = await _acquire_connection()
            async with ctx as conn:
                cursor = await conn.execute(
                    "SELECT user_id FROM users WHERE LOWER(username) = ?",
                    (trusted_username.lower(),),
                )
                row = await cursor.fetchone()
                if not row:
                    raise ValueError(f"Trusted user {trusted_username} not found")
                trusted_user_id = row["user_id"]
                await conn.execute(
                    """
                    INSERT OR IGNORE INTO trusted_users (user_id, trusted_user_id)
                    VALUES (?, ?)
                    """,
                    (user_id, trusted_user_id),
                )
                await conn.commit()
        except Exception as e:
            logger.exception(
                "Failed to add trust from user %d to %s: %s",
                user_id,
                trusted_username,
                e,
            )
            raise

    @classmethod
    async def trusts(cls, user_id: int, other_username: str) -> bool:
        """
        Check if user_id trusts the user with username other_username.
        """
        try:
            ctx = await _acquire_connection()
            async with ctx as conn:
                cursor = await conn.execute(
                    """
                    SELECT 1 FROM trusted_users tu
                    JOIN users u ON tu.trusted_user_id = u.user_id
                    WHERE tu.user_id = ? AND LOWER(u.username) = ?
                    LIMIT 1
                    """,
                    (user_id, other_username.lower()),
                )
                row = await cursor.fetchone()
                return row is not None
        except Exception as e:
            logger.exception(
                "Failed to check trust from user %d to %s: %s",
                user_id,
                other_username,
                e,
            )
            raise

    @classmethod
    async def list_trusted(cls, user_id: int) -> List[UserModel]:
        """List all users trusted by the given user."""
        try:
            ctx = await _acquire_connection()
            async with ctx as conn:
                cursor = await conn.execute(
                    """
                    SELECT u.* FROM trusted_users tu
                    JOIN users u ON tu.trusted_user_id = u.user_id
                    WHERE tu.user_id = ?
                    ORDER BY u.username
                    """,
                    (user_id,),
                )
                rows = await cursor.fetchall()
                return [UserModel(**dict(row)) for row in rows]  # type: ignore
        except Exception as e:
            logger.exception("Failed to list trusted users for %d: %s", user_id, e)
            raise

    @classmethod
    async def remove_trust(cls, user_id: int, trusted_username: str) -> None:
        """Remove trust relationship between users."""
        try:
            ctx = await _acquire_connection()
            async with ctx as conn:
                # Find trusted user's id
                cursor = await conn.execute(
                    "SELECT user_id FROM users WHERE LOWER(username) = ?",
                    (trusted_username.lower(),),
                )
                row = await cursor.fetchone()
                if not row:
                    raise ValueError(f"Trusted user {trusted_username} not found")
                trusted_user_id = row["user_id"]

                await conn.execute(
                    """
                    DELETE FROM trusted_users
                    WHERE user_id = ? AND trusted_user_id = ?
                    """,
                    (user_id, trusted_user_id),
                )
                await conn.commit()
        except Exception as e:
            logger.exception(
                "Failed to remove trust from user %d to %s: %s",
                user_id,
                trusted_username,
                e,
            )
            raise


class DebtRepository:
    """SQLite implementation of debt repository."""

    @classmethod
    async def add(cls, *, creditor_id: int, debtor_id: int, amount: int, description: str) -> DebtModel:
        """Create a new debt record."""
        try:
            ctx = await _acquire_connection()
            async with ctx as conn:
                cursor = await conn.execute(
                    """
                    INSERT INTO debts (creditor_id, debtor_id, amount, description)
                    VALUES (?, ?, ?, ?)
                    """,
                    (creditor_id, debtor_id, amount, description),
                )
                await conn.commit()
                debt_id = cursor.lastrowid
                cursor = await conn.execute("SELECT * FROM debts WHERE debt_id = ?", (debt_id,))
                row = await cursor.fetchone()
                return DebtModel(**dict(row))  # type: ignore
        except Exception as e:
            logger.exception(
                "Failed to add debt creditor=%d debtor=%d: %s",
                creditor_id,
                debtor_id,
                e,
            )
            raise

    @classmethod
    async def list_active_by_user(cls, user_id: int) -> List[DebtModel]:
        """List all active debts where user is creditor or debtor."""
        try:
            ctx = await _acquire_connection()
            async with ctx as conn:
                cursor = await conn.execute(
                    """
                    SELECT * FROM debts
                    WHERE status = 'active'
                      AND (creditor_id = ? OR debtor_id = ?)
                    ORDER BY created_at DESC
                    """,
                    (user_id, user_id),
                )
                rows = await cursor.fetchall()
                return [DebtModel(**dict(row)) for row in rows]  # type: ignore
        except Exception as e:
            logger.exception("Failed to list active debts for user %d: %s", user_id, e)
            raise

    @classmethod
    async def list_active_between(cls, creditor_id: int, debtor_id: int) -> List[DebtModel]:
        """List active debts for a specific creditor/debtor pair."""
        try:
            ctx = await _acquire_connection()
            async with ctx as conn:
                cursor = await conn.execute(
                    """
                    SELECT * FROM debts
                    WHERE status = 'active'
                      AND creditor_id = ? AND debtor_id = ?
                    ORDER BY created_at ASC
                    """,
                    (creditor_id, debtor_id),
                )
                rows = await cursor.fetchall()
                return [DebtModel(**dict(row)) for row in rows]  # type: ignore
        except Exception as e:
            logger.exception(
                "Failed to list active debts between %d and %d: %s",
                creditor_id,
                debtor_id,
                e,
            )
            raise

    @classmethod
    async def get(cls, debt_id: int) -> Optional[DebtModel]:
        """Get a debt by its ID."""
        try:
            ctx = await _acquire_connection()
            async with ctx as conn:
                cursor = await conn.execute("SELECT * FROM debts WHERE debt_id = ?", (debt_id,))
                row = await cursor.fetchone()
                if row:
                    return DebtModel(**dict(row))  # type: ignore
                return None
        except Exception as e:
            logger.exception("Failed to get debt %d: %s", debt_id, e)
            raise

    @classmethod
    async def update_status(cls, debt_id: int, status: DebtStatusLiteral) -> DebtModel:
        """Update the status of a debt."""
        if status not in {"pending", "active", "paid", "rejected"}:
            raise ValueError(f"Invalid status: {status}")
        try:
            ctx = await _acquire_connection()
            async with ctx as conn:
                await conn.execute(
                    "UPDATE debts SET status = ? WHERE debt_id = ?",
                    (status, debt_id),
                )
                await conn.commit()
                cursor = await conn.execute("SELECT * FROM debts WHERE debt_id = ?", (debt_id,))
                row = await cursor.fetchone()
                if row is None:
                    raise ValueError("Debt not found")
                return DebtModel(**dict(row))  # type: ignore
        except Exception as e:
            logger.exception("Failed to update status for debt %d: %s", debt_id, e)
            raise

    @classmethod
    async def update_amount(cls, debt_id: int, amount: int) -> DebtModel:
        """Update the amount of a debt."""
        if amount <= 0:
            raise ValueError("Amount must be positive")
        try:
            ctx = await _acquire_connection()
            async with ctx as conn:
                await conn.execute(
                    "UPDATE debts SET amount = ? WHERE debt_id = ?",
                    (amount, debt_id),
                )
                await conn.commit()
                cursor = await conn.execute(
                    "SELECT * FROM debts WHERE debt_id = ?",
                    (debt_id,),
                )
                row = await cursor.fetchone()
                if row is None:
                    raise ValueError("Debt not found")
                return DebtModel(**dict(row))  # type: ignore
        except Exception as e:
            logger.exception("Failed to update amount for debt %d: %s", debt_id, e)
            raise


class PaymentRepository:
    """SQLite implementation of payment repository."""

    @classmethod
    async def create_payment(cls, debt_id: int, amount: int) -> PaymentModel:
        """Create a new payment record for a debt."""
        if amount <= 0:
            raise ValueError("Amount must be positive")
        try:
            ctx = await _acquire_connection()
            async with ctx as conn:
                # ensure debt exists
                cursor = await conn.execute(
                    "SELECT 1 FROM debts WHERE debt_id = ?",
                    (debt_id,),
                )
                if await cursor.fetchone() is None:
                    raise ValueError("Debt not found")

                cursor = await conn.execute(
                    """
                    INSERT INTO payments (debt_id, amount)
                    VALUES (?, ?)
                    """,
                    (debt_id, amount),
                )
                await conn.commit()
                payment_id = cursor.lastrowid
                cursor = await conn.execute("SELECT * FROM payments WHERE payment_id = ?", (payment_id,))
                row = await cursor.fetchone()
                return PaymentModel(**dict(row))  # type: ignore
        except Exception as e:
            logger.exception("Failed to create payment for debt %d: %s", debt_id, e)
            raise

    @classmethod
    async def get_by_debt(cls, debt_id: int) -> List[PaymentModel]:
        """Get all payments for a specific debt."""
        try:
            ctx = await _acquire_connection()
            async with ctx as conn:
                cursor = await conn.execute(
                    """
                    SELECT * FROM payments
                    WHERE debt_id = ?
                    ORDER BY created_at ASC
                    """,
                    (debt_id,),
                )
                rows = await cursor.fetchall()
                return [PaymentModel(**dict(row)) for row in rows]  # type: ignore
        except Exception as e:
            logger.exception("Failed to get payments for debt %d: %s", debt_id, e)
            raise

    @classmethod
    async def get(cls, payment_id: int) -> Optional[PaymentModel]:
        """Retrieve a payment by its ID."""
        try:
            ctx = await _acquire_connection()
            async with ctx as conn:
                cursor = await conn.execute(
                    "SELECT * FROM payments WHERE payment_id = ?",
                    (payment_id,),
                )
                row = await cursor.fetchone()
                return PaymentModel(**dict(row)) if row else None  # type: ignore
        except Exception as e:
            logger.exception("Failed to get payment %d: %s", payment_id, e)
            raise

    @classmethod
    async def delete(cls, payment_id: int) -> None:
        """Delete a payment record."""
        try:
            ctx = await _acquire_connection()
            async with ctx as conn:
                await conn.execute("DELETE FROM payments WHERE payment_id = ?", (payment_id,))
                await conn.commit()
        except Exception as e:
            logger.exception("Failed to delete payment %d: %s", payment_id, e)
            raise

    @classmethod
    async def confirm_payment(cls, payment_id: int) -> PaymentModel:
        """Confirm a pending payment."""
        try:
            ctx = await _acquire_connection()
            async with ctx as conn:
                await conn.execute(
                    """
                    UPDATE payments
                    SET status = 'confirmed',
                        confirmed_at = CURRENT_TIMESTAMP
                    WHERE payment_id = ?
                    """,
                    (payment_id,),
                )
                await conn.commit()
                cursor = await conn.execute("SELECT * FROM payments WHERE payment_id = ?", (payment_id,))
                row = await cursor.fetchone()
                if row is None:
                    raise ValueError("Payment not found")
                return PaymentModel(**dict(row))  # type: ignore
        except Exception as e:
            logger.exception("Failed to confirm payment %d: %s", payment_id, e)
            raise


class TrustedUserRepository:
    """SQLite implementation of trusted user repository."""

    @classmethod
    async def add_trust(cls, user_id: int, trusted_user_id: int) -> None:
        """Add a trust relationship."""
        try:
            ctx = await _acquire_connection()
            async with ctx as conn:
                await conn.execute(
                    """
                    INSERT OR IGNORE INTO trusted_users (user_id, trusted_user_id)
                    VALUES (?, ?)
                    """,
                    (user_id, trusted_user_id),
                )
                await conn.commit()
        except Exception as e:
            logger.exception(
                "Failed to add trusted user %d for user %d: %s",
                trusted_user_id,
                user_id,
                e,
            )
            raise

    @classmethod
    async def remove_trust(cls, user_id: int, trusted_user_id: int) -> None:
        """Remove a trust relationship."""
        try:
            ctx = await _acquire_connection()
            async with ctx as conn:
                await conn.execute(
                    """
                    DELETE FROM trusted_users
                    WHERE user_id = ? AND trusted_user_id = ?
                    """,
                    (user_id, trusted_user_id),
                )
                await conn.commit()
        except Exception as e:
            logger.exception(
                "Failed to remove trusted user %d for user %d: %s",
                trusted_user_id,
                user_id,
                e,
            )
            raise

    @classmethod
    async def list_trusted(cls, user_id: int) -> List[UserModel]:
        """List all users trusted by the given user."""
        try:
            ctx = await _acquire_connection()
            async with ctx as conn:
                cursor = await conn.execute(
                    """
                    SELECT u.* FROM trusted_users tu
                    JOIN users u ON tu.trusted_user_id = u.user_id
                    WHERE tu.user_id = ?
                    ORDER BY u.username
                    """,
                    (user_id,),
                )
                rows = await cursor.fetchall()
                return [UserModel(**dict(row)) for row in rows]  # type: ignore
        except Exception as e:
            logger.exception("Failed to list trusted users for %d: %s", user_id, e)
            raise
