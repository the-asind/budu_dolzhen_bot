"""Debt confirmation workflow tests.

These tests drive Issue 3 logic: pending confirmation, manual acceptance,
and auto-accept when debtor trusts creditor.
"""

from datetime import timedelta

import asyncio
import pytest  # type: ignore

from bot.core import DebtManager
from bot.db.repositories import DebtRepository, UserRepository

AUTHOR = "creditor"
DEBTOR = "debtor1"


@pytest.mark.asyncio
async def test_debt_is_pending_after_creation() -> None:
    # reset state
    DebtRepository._debts.clear()  # pylint: disable=protected-access
    UserRepository._users.clear()  # type: ignore[attr-defined]
    UserRepository._auto_inc = 1  # type: ignore[attr-defined]

    debts = await DebtManager.process_message(f"@{DEBTOR} 500 ужин", author_username=AUTHOR)
    assert len(debts) == 1
    debt = debts[0]

    assert debt.status == "pending"


@pytest.mark.asyncio
async def test_manual_confirmation_changes_status() -> None:
    DebtRepository._debts.clear()  # pylint: disable=protected-access
    UserRepository._users.clear()  # type: ignore[attr-defined]
    UserRepository._auto_inc = 1  # type: ignore[attr-defined]

    debts = await DebtManager.process_message(f"@{DEBTOR} 500 ужин", author_username=AUTHOR)
    debt = debts[0]

    # simulate debtor confirming
    updated = await DebtManager.confirm_debt(debt.debt_id, debtor_username=DEBTOR)
    assert updated.status == "active"


@pytest.mark.asyncio
async def test_auto_confirmation_when_trusted() -> None:
    DebtRepository._debts.clear()  # pylint: disable=protected-access
    UserRepository._users.clear()  # type: ignore[attr-defined]
    UserRepository._auto_inc = 1  # type: ignore[attr-defined]

    # author adds debtor to trusted list
    author_user = await UserRepository.add(AUTHOR)  # this user will become debtor
    debtor_user = await UserRepository.add(DEBTOR)  # author of message (creditor)

    # Debtor (author_user) trusts creditor (debtor_user.username)
    await UserRepository.add_trust(author_user.user_id, debtor_user.username)

    debts = await DebtManager.process_message(f"@{AUTHOR} 800 кино", author_username=DEBTOR)
    debt = debts[0]
    assert debt.status == "active"  # auto-accepted because debtor trusts creditor 