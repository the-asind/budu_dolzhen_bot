"""Debt management business logic (MVP, TDD slice)."""

from __future__ import annotations

from typing import List
from datetime import timezone, datetime

from bot.db.models import Debt, DebtStatus
from bot.db.repositories import (
    DebtRepository,
    UserRepository
)

from .debt_parser import DebtParser

STATUS_ACTIVE = "active"
STATUS_PENDING = "pending"


class DebtManager:  # pylint: disable=too-few-public-methods
    """High-level façade for debt-related operations."""

    @staticmethod
    async def process_message(message: str, *, author_username: str) -> List[Debt]:
        """Parse *message*, create `Debt` records and return them."""

        author = await UserRepository.get_by_username(author_username)
        if author is None:
            author = await UserRepository.add(author_username)

        parsed = DebtParser.parse(message, author_username=author_username)

        created: List[Debt] = []
        for debtor_username, pd in parsed.items():
            debtor = await UserRepository.get_by_username(debtor_username)
            if debtor is None:
                debtor = await UserRepository.add(debtor_username)

            status = (
                STATUS_ACTIVE
                if await UserRepository.trusts(debtor.user_id, author_username)
                else STATUS_PENDING
            )

            debt = await DebtRepository.add(
                creditor_id=author.user_id,
                debtor_id=debtor.user_id,
                amount=pd.amount,
                description=pd.combined_comment,
            )

            if status == STATUS_ACTIVE:
                debt = await DebtRepository.update_status(debt.debt_id, STATUS_ACTIVE)

            created.append(debt)

        return created


    @staticmethod
    async def confirm_debt(debt_id: int, *, debtor_username: str) -> Debt:
        """Debtor accepts the debt, transitioning it to ACTIVE."""

        debt = await DebtRepository.get(debt_id)
        if debt is None:
            raise ValueError("Debt not found")

        debtor = await UserRepository.get_by_username(debtor_username)
        if debtor is None or debtor.user_id != debt.debtor_id:
            raise ValueError("Only debtor can confirm debt")

        debt = await DebtRepository.update_status(debt_id, STATUS_ACTIVE)
        return debt
