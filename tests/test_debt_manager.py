"""DebtManager unit tests (initial TDD slice)."""

import pytest
import pytest_asyncio
from unittest.mock import patch

from bot.core import DebtManager
from bot.db.repositories import UserRepository
from bot.db import connection

AUTHOR_USERNAME = "creditor"


@pytest_asyncio.fixture
async def db_setup():
    """Create in-memory SQLite database for tests."""
    with patch.object(connection, "DATABASE_PATH", ":memory:"):
        # Reset pool to ensure new in-memory db is used
        connection._pool = None
        connection._pool_initialized = False
        yield
        connection._pool = None
        connection._pool_initialized = False


@pytest.mark.usefixtures("db_setup")
@pytest.mark.asyncio
async def test_process_message_creates_debts() -> None:
    message = "@debtor1 500 ужин\n@debtor2 250 кофе"

    # We need to create the users first, as the manager expects them to exist
    await UserRepository.add(AUTHOR_USERNAME)
    await UserRepository.add("debtor1")
    await UserRepository.add("debtor2")

    debts = await DebtManager.process_message(message, author_username=AUTHOR_USERNAME)

    assert len(debts) == 2
    amounts = sorted(d.amount for d in debts)
    assert amounts == [25000, 50000]


@pytest.mark.usefixtures("db_setup")
@pytest.mark.asyncio
async def test_existing_users_reused() -> None:
    author = await UserRepository.add(AUTHOR_USERNAME)
    debtor = await UserRepository.add("debtor3")

    message = "@debtor3 100 тест"

    debts = await DebtManager.process_message(message, author_username=AUTHOR_USERNAME)
    debt = debts[0]

    assert debt.creditor_id == author.user_id
    assert debt.debtor_id == debtor.user_id
    assert debt.amount == 10000
    assert debt.status == "pending"
