"""Debt management business logic (MVP, TDD slice)."""

from __future__ import annotations

from typing import List

from bot.db.models import Debt
from bot.db.repositories import DebtRepository, UserRepository

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

            status = STATUS_ACTIVE if await UserRepository.trusts(debtor.user_id, author_username) else STATUS_PENDING

            debt = await DebtRepository.add(
                creditor_id=author.user_id,
                debtor_id=debtor.user_id,
                amount=pd.amount,
                description=pd.combined_comment,
            )

            if status == STATUS_ACTIVE:
                debt = await DebtRepository.update_status(debt.debt_id, STATUS_ACTIVE)
                debt = await DebtManager._merge_same_direction(debt)
                debt = await DebtManager._offset_opposite(debt)

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

        debt = await DebtManager._merge_same_direction(debt)
        if debt.status != STATUS_ACTIVE:
            debt = await DebtRepository.update_status(debt.debt_id, STATUS_ACTIVE)

        debt = await DebtManager._offset_opposite(debt)
        return debt

    @staticmethod
    async def _merge_same_direction(debt: Debt) -> Debt:
        """Combine with existing active debt from the same creditor to debtor."""

        existing = await DebtRepository.list_active_between(debt.creditor_id, debt.debtor_id)
        for current in existing:
            if current.debt_id != debt.debt_id:
                updated = await DebtRepository.update_amount(current.debt_id, current.amount + debt.amount)
                await DebtRepository.update_status(debt.debt_id, "paid")
                return updated
        return debt

    @staticmethod
    async def _offset_opposite(debt: Debt) -> Debt:
        """Offset active debt against debts in the opposite direction."""

        opposite = await DebtRepository.list_active_between(
            creditor_id=debt.debtor_id,
            debtor_id=debt.creditor_id,
        )

        remaining = debt.amount
        for od in opposite:
            if remaining == 0:
                break
            if od.amount > remaining:
                await DebtRepository.update_amount(od.debt_id, od.amount - remaining)
                debt = await DebtRepository.update_status(debt.debt_id, "paid")
                remaining = 0
            else:
                remaining -= od.amount
                await DebtRepository.update_status(od.debt_id, "paid")

        if remaining == 0:
            if debt.status != "paid":
                debt = await DebtRepository.update_status(debt.debt_id, "paid")
        elif remaining != debt.amount:
            debt = await DebtRepository.update_amount(debt.debt_id, remaining)

        return debt
