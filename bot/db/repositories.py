"""In-memory repository stubs (TDD placeholder).

NOTE: These classes are **not** thread-safe and are intended **only for tests
and early prototyping**. They will be replaced with SQLite implementations that
use `aiosqlite` once the database schema and migrations are finalised.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Set


class DebtStatus(str, Enum):
    """Lifecycle states for a debt record."""

    PENDING = "pending"
    ACTIVE = "active"
    REJECTED = "rejected"


@dataclass
class User:
    user_id: int
    username: str
    trusted: Set[str] = field(default_factory=set)  # usernames this user trusts


@dataclass
class Debt:
    debt_id: int
    creditor_id: int
    debtor_id: int
    amount: int  # minimal units (e.g. kopecks)
    description: str
    status: DebtStatus = DebtStatus.PENDING
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class UserRepository:  # pylint: disable=too-few-public-methods
    """Extremely simple in-memory user store."""

    _auto_inc: int = 1
    _users: Dict[int, User] = {}

    @classmethod
    async def add(cls, username: str) -> User:
        uid = cls._auto_inc
        cls._auto_inc += 1
        user = User(user_id=uid, username=username)
        cls._users[uid] = user
        return user

    @classmethod
    async def get_by_id(cls, user_id: int) -> User | None:  # noqa: D401
        return cls._users.get(user_id)

    @classmethod
    async def get_by_username(cls, username: str) -> User | None:  # noqa: D401
        for user in cls._users.values():
            if user.username == username:
                return user
        return None

    @classmethod
    async def add_trust(cls, user_id: int, trusted_username: str) -> None:
        user = cls._users[user_id]
        user.trusted.add(trusted_username)

    @classmethod
    async def trusts(cls, user_id: int, other_username: str) -> bool:
        user = cls._users[user_id]
        return other_username in user.trusted


class DebtRepository:  # pylint: disable=too-few-public-methods
    """In-memory debt records store."""

    _auto_inc: int = 1
    _debts: Dict[int, Debt] = {}

    @classmethod
    async def add(
        cls, *, creditor_id: int, debtor_id: int, amount: int, description: str
    ) -> Debt:
        did = cls._auto_inc
        cls._auto_inc += 1
        debt = Debt(
            debt_id=did,
            creditor_id=creditor_id,
            debtor_id=debtor_id,
            amount=amount,
            description=description,
            status=DebtStatus.PENDING,
            created_at=datetime.now(timezone.utc),
        )
        cls._debts[did] = debt
        return debt

    @classmethod
    async def list_active_by_user(cls, user_id: int) -> List[Debt]:  # noqa: D401
        return [
            d
            for d in cls._debts.values()
            if d.status == DebtStatus.ACTIVE and (d.creditor_id == user_id or d.debtor_id == user_id)
        ]

    @classmethod
    async def get(cls, debt_id: int) -> Debt | None:
        return cls._debts.get(debt_id)

    @classmethod
    async def update_status(cls, debt_id: int, status: DebtStatus) -> Debt:
        debt = cls._debts[debt_id]
        debt.status = status
        return debt 