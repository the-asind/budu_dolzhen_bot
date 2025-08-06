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


@pytest.mark.asyncio
async def test_confirm_debt_offsets_existing_opposite_debt() -> None:
    """Confirming a debt should offset any active debt in the opposite direction."""
    user1 = await UserRepository.add("user1")
    user2 = await UserRepository.add("user2")

    existing = await DebtRepository.add(
        creditor_id=user2.user_id,
        debtor_id=user1.user_id,
        amount=2000,
        description="initial",
    )
    await DebtRepository.update_status(existing.debt_id, "active")

    reverse = await DebtRepository.add(
        creditor_id=user1.user_id,
        debtor_id=user2.user_id,
        amount=1000,
        description="reverse",
    )

    confirmed = await DebtManager.confirm_debt(reverse.debt_id, debtor_username="user2")
    assert confirmed.status == "paid"

    updated = await DebtRepository.get(existing.debt_id)
    assert updated.amount == 1000
    assert updated.status == "active"


@pytest.mark.asyncio
async def test_confirm_debt_offsets_and_reduces_new_debt() -> None:
    """Remaining amount should stay with new debt if it's larger than existing."""
    user1 = await UserRepository.add("alpha")
    user2 = await UserRepository.add("beta")

    existing = await DebtRepository.add(
        creditor_id=user1.user_id,
        debtor_id=user2.user_id,
        amount=500,
        description="initial",
    )
    await DebtRepository.update_status(existing.debt_id, "active")

    reverse = await DebtRepository.add(
        creditor_id=user2.user_id,
        debtor_id=user1.user_id,
        amount=1000,
        description="reverse",
    )

    confirmed = await DebtManager.confirm_debt(reverse.debt_id, debtor_username="alpha")
    assert confirmed.status == "active"
    assert confirmed.amount == 500

    updated = await DebtRepository.get(existing.debt_id)
    assert updated.status == "paid"


@pytest.mark.asyncio
async def test_confirm_debt_merges_existing_same_direction_debt() -> None:
    """Confirming a debt should increase existing active debt instead of creating another."""

    user1 = await UserRepository.add("gamma")
    user2 = await UserRepository.add("delta")

    existing = await DebtRepository.add(
        creditor_id=user1.user_id,
        debtor_id=user2.user_id,
        amount=700,
        description="first",
    )
    await DebtRepository.update_status(existing.debt_id, "active")

    new_debt = await DebtRepository.add(
        creditor_id=user1.user_id,
        debtor_id=user2.user_id,
        amount=300,
        description="second",
    )

    merged = await DebtManager.confirm_debt(new_debt.debt_id, debtor_username="delta")
    assert merged.debt_id == existing.debt_id
    assert merged.amount == 1000
    assert merged.status == "active"

    updated_new = await DebtRepository.get(new_debt.debt_id)
    assert updated_new.status == "paid"
