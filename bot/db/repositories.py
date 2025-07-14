"""SQLite repository implementations using aiosqlite."""

from __future__ import annotations

import logging
from typing import List, Optional

from .connection import get_connection
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
            async with get_connection() as conn:
                cursor = await conn.execute(
                    """
                    INSERT INTO users (username, first_name)
                    VALUES (?, ?)
                    """,
                    (username, username),
                )
                await conn.commit()
                user_id = cursor.lastrowid
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
            async with get_connection() as conn:
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
            async with get_connection() as conn:
                cursor = await conn.execute(
                    "SELECT * FROM users WHERE username = ?",
                    (username,),
                )
                row = await cursor.fetchone()
                if row:
                    return UserModel(**dict(row))  # type: ignore
                return None
        except Exception as e:
            logger.exception("Failed to get user by username %s: %s", username, e)
            raise

    @classmethod
    async def update_user_language(cls, user_id: int, language_code: str) -> None:
        """Update user's language preference."""
        try:
            async with get_connection() as conn:
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
            async with get_connection() as conn:
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
            async with get_connection() as conn:
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
            async with get_connection() as conn:
                cursor = await conn.execute(
                    "SELECT user_id FROM users WHERE username = ?",
                    (trusted_username,),
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
                "Failed to add trust from user %d to %s: %s", user_id, trusted_username, e
            )
            raise

    @classmethod
    async def trusts(cls, user_id: int, other_username: str) -> bool:
        """
        Check if user_id trusts the user with username other_username.
        """
        try:
            async with get_connection() as conn:
                cursor = await conn.execute(
                    """
                    SELECT 1 FROM trusted_users tu
                    JOIN users u ON tu.trusted_user_id = u.user_id
                    WHERE tu.user_id = ? AND u.username = ?
                    LIMIT 1
                    """,
                    (user_id, other_username),
                )
                row = await cursor.fetchone()
                return row is not None
        except Exception as e:
            logger.exception(
                "Failed to check trust from user %d to %s: %s", user_id, other_username, e
            )
            raise

    @classmethod
    async def list_trusted(cls, user_id: int) -> List[UserModel]:
        """List all users trusted by the given user."""
        try:
            async with get_connection() as conn:
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
            async with get_connection() as conn:
                # Find trusted user's id
                cursor = await conn.execute(
                    "SELECT user_id FROM users WHERE username = ?",
                    (trusted_username,),
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
                "Failed to remove trust from user %d to %s: %s", user_id, trusted_username, e
            )
            raise


class DebtRepository:
    """SQLite implementation of debt repository."""

    @classmethod
    async def add(
        cls, *, creditor_id: int, debtor_id: int, amount: int, description: str
    ) -> DebtModel:
        """Create a new debt record."""
        try:
            async with get_connection() as conn:
                cursor = await conn.execute(
                    """
                    INSERT INTO debts (creditor_id, debtor_id, amount, description)
                    VALUES (?, ?, ?, ?)
                    """,
                    (creditor_id, debtor_id, amount, description),
                )
                await conn.commit()
                debt_id = cursor.lastrowid
                cursor = await conn.execute(
                    "SELECT * FROM debts WHERE debt_id = ?", (debt_id,)
                )
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
            async with get_connection() as conn:
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
    async def get(cls, debt_id: int) -> Optional[DebtModel]:
        """Get a debt by its ID."""
        try:
            async with get_connection() as conn:
                cursor = await conn.execute(
                    "SELECT * FROM debts WHERE debt_id = ?", (debt_id,)
                )
                row = await cursor.fetchone()
                if row:
                    return DebtModel(**dict(row))  # type: ignore
                return None
        except Exception as e:
            logger.exception("Failed to get debt %d: %s", debt_id, e)
            raise

    @classmethod
    async def update_status(
        cls, debt_id: int, status: DebtStatusLiteral
    ) -> DebtModel:
        """Update the status of a debt."""
        try:
            async with get_connection() as conn:
                await conn.execute(
                    "UPDATE debts SET status = ? WHERE debt_id = ?",
                    (status, debt_id),
                )
                await conn.commit()
                cursor = await conn.execute(
                    "SELECT * FROM debts WHERE debt_id = ?", (debt_id,)
                )
                row = await cursor.fetchone()
                return DebtModel(**dict(row))  # type: ignore
        except Exception as e:
            logger.exception("Failed to update status for debt %d: %s", debt_id, e)
            raise


class PaymentRepository:
    """SQLite implementation of payment repository."""

    @classmethod
    async def create_payment(cls, debt_id: int, amount: int) -> PaymentModel:
        """Create a new payment record for a debt."""
        try:
            async with get_connection() as conn:
                cursor = await conn.execute(
                    """
                    INSERT INTO payments (debt_id, amount)
                    VALUES (?, ?)
                    """,
                    (debt_id, amount),
                )
                await conn.commit()
                payment_id = cursor.lastrowid
                cursor = await conn.execute(
                    "SELECT * FROM payments WHERE payment_id = ?", (payment_id,)
                )
                row = await cursor.fetchone()
                return PaymentModel(**dict(row))  # type: ignore
        except Exception as e:
            logger.exception(
                "Failed to create payment for debt %d: %s", debt_id, e
            )
            raise

    @classmethod
    async def get_by_debt(cls, debt_id: int) -> List[PaymentModel]:
        """Get all payments for a specific debt."""
        try:
            async with get_connection() as conn:
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
    async def confirm_payment(cls, payment_id: int) -> PaymentModel:
        """Confirm a pending payment."""
        try:
            async with get_connection() as conn:
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
                cursor = await conn.execute(
                    "SELECT * FROM payments WHERE payment_id = ?", (payment_id,)
                )
                row = await cursor.fetchone()
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
            async with get_connection() as conn:
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
            async with get_connection() as conn:
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
            async with get_connection() as conn:
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
