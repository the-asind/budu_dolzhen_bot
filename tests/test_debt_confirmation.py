"""Debt confirmation workflow tests.

These tests drive Issue 3 logic: pending confirmation, manual acceptance,
and auto-accept when debtor trusts creditor.
"""

import pytest  # type: ignore

from bot.core import DebtManager
from bot.db.repositories import DebtRepository, UserRepository

AUTHOR = "creditor"
DEBTOR = "debtor1"


@pytest.mark.asyncio
async def test_debt_is_pending_after_creation() -> None:
    debts = await DebtManager.process_message(f"@{DEBTOR} 500 ужин", author_username=AUTHOR)
    assert len(debts) == 1
    debt = debts[0]

    assert debt.status == "pending"


@pytest.mark.asyncio
async def test_manual_confirmation_changes_status() -> None:
    debts = await DebtManager.process_message(f"@{DEBTOR} 500 ужин", author_username=AUTHOR)
    debt = debts[0]

    # simulate debtor confirming
    updated = await DebtManager.confirm_debt(debt.debt_id, debtor_username=DEBTOR)
    assert updated.status == "active"


@pytest.mark.asyncio
async def test_auto_confirmation_when_trusted() -> None:
    # Setup both users: creditor and debtor
    creditor_user = await UserRepository.add(AUTHOR)
    debtor_user = await UserRepository.add(DEBTOR)

    # Debtor trusts creditor, so debts from creditor should auto-confirm
    if creditor_user.username:
        await UserRepository.add_trust(debtor_user.user_id, creditor_user.username)

    # Diagnostic: verify trust relationship is properly established
    trust_exists = await UserRepository.trusts(debtor_user.user_id, AUTHOR)
    assert trust_exists, f"Expected trust relationship: debtor '{DEBTOR}' should trust creditor '{AUTHOR}'"
    # Debug output for trust relationship
    print(f"Debug: trust_exists={trust_exists} (debtor={debtor_user.user_id}, creditor='{AUTHOR}')")

    # Ensure no pre-existing debts for clarity
    existing = await DebtRepository.list_active_by_user(debtor_user.user_id)
    # Debug output for existing debts before creation
    print(f"Debug: existing active debts for debtor before creation = {existing}")

    # Process a new debt creation
    debts = await DebtManager.process_message(f"@{DEBTOR} 800 кино", author_username=AUTHOR)
    assert len(debts) == 1, f"Expected exactly one debt created, got {len(debts)}"
    debt = debts[0]

    # Debug output for debt status after creation
    print(f"Debug: debt.status={debt.status} (debt_id={debt.debt_id})")
    # When debtor trusts the creditor the debt should be active immediately
    assert debt.status == "active"
