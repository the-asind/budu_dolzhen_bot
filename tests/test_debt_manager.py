"""DebtManager unit tests (initial TDD slice)."""

import pytest  # type: ignore

from bot.core import DebtManager
from bot.db.repositories import UserRepository, DebtRepository

AUTHOR_USERNAME = "creditor"


@pytest.mark.asyncio
async def test_process_message_creates_debts() -> None:
    message = "@debtor1 500 ужин\n@debtor2 250 кофе"

    # Reset repositories for test isolation
    DebtRepository._debts.clear()  # pylint: disable=protected-access
    UserRepository._users.clear()  # type: ignore[attr-defined]
    UserRepository._auto_inc = 1  # type: ignore[attr-defined]

    debts = await DebtManager.process_message(message, author_username=AUTHOR_USERNAME)

    assert len(debts) == 2
    amounts = sorted(d.amount for d in debts)
    assert amounts == [250, 500]
    assert len(DebtRepository._debts) == 2  # pylint: disable=protected-access


@pytest.mark.asyncio
async def test_existing_users_reused() -> None:
    # Reset repositories
    DebtRepository._debts.clear()  # pylint: disable=protected-access
    UserRepository._users.clear()  # type: ignore[attr-defined]
    UserRepository._auto_inc = 1  # type: ignore[attr-defined]

    author = await UserRepository.add(AUTHOR_USERNAME)
    debtor = await UserRepository.add("debtor3")

    message = "@debtor3 100 тест"

    debts = await DebtManager.process_message(message, author_username=AUTHOR_USERNAME)
    debt = debts[0]

    assert debt.creditor_id == author.user_id
    assert debt.debtor_id == debtor.user_id
    assert debt.amount == 100
    assert debt.status == "pending" 