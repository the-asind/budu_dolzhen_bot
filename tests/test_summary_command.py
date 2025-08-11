import pytest
from unittest.mock import AsyncMock, patch

from bot.handlers.debt_handlers import handle_summary_command
from bot.db.models import Debt, Payment, User

pytestmark = pytest.mark.asyncio


async def test_summary_no_debts(model_message):
    message = model_message(text="/summary")
    message.reply = AsyncMock()
    with patch("bot.handlers.debt_handlers.DebtRepository") as repo, patch(
        "bot.handlers.debt_handlers._", lambda k, **kwargs: k
    ):
        repo.list_active_by_user = AsyncMock(return_value=[])
        await handle_summary_command(message, lambda key, **kwargs: key)
        repo.list_active_by_user.assert_called_once_with(message.from_user.id)
        message.reply.assert_called_once_with("summary_none")


async def test_summary_with_debts(model_message, model_user):
    user = model_user(id=1, username="me")
    message = model_message(text="/summary", from_user=user)
    message.reply = AsyncMock()
    debt1 = Debt(debt_id=1, creditor_id=2, debtor_id=1, amount=1500, description="", status="active")
    debt2 = Debt(debt_id=2, creditor_id=1, debtor_id=3, amount=500, description="", status="active")
    with patch("bot.handlers.debt_handlers.DebtRepository") as repo, patch(
        "bot.handlers.debt_handlers.user_repo"
    ) as urepo, patch(
        "bot.handlers.debt_handlers.PaymentRepository.get_by_debt",
        AsyncMock(return_value=[]),
    ), patch(
        "bot.handlers.debt_handlers._", lambda k, **kwargs: k
    ):
        repo.list_active_by_user = AsyncMock(return_value=[debt1, debt2])
        urepo.get_by_id = AsyncMock(
            side_effect=[
                User(user_id=2, username="alice", first_name="a"),
                User(user_id=3, username="bob", first_name="b"),
            ]
        )
        await handle_summary_command(message, lambda key, **kwargs: key)
        message.reply.assert_called_once()
        text = message.reply.call_args[0][0]
        assert "@alice" in text
        assert "@bob" in text


async def test_summary_with_pending_payments(model_message, model_user):
    user = model_user(id=1, username="me")
    message = model_message(text="/summary", from_user=user)
    message.reply = AsyncMock()
    debt = Debt(debt_id=1, creditor_id=1, debtor_id=2, amount=1000, description="", status="active")
    payment = Payment(payment_id=1, debt_id=1, amount=300, status="pending_confirmation")
    with patch("bot.handlers.debt_handlers.DebtRepository") as repo, patch(
        "bot.handlers.debt_handlers.user_repo"
    ) as urepo, patch(
        "bot.handlers.debt_handlers.PaymentRepository.get_by_debt",
        AsyncMock(return_value=[payment]),
    ), patch(
        "bot.handlers.debt_handlers._", lambda k, **kwargs: k
    ):
        repo.list_active_by_user = AsyncMock(return_value=[debt])
        urepo.get_by_id = AsyncMock(return_value=User(user_id=2, username="alice", first_name="a"))
        await handle_summary_command(message, lambda key, **kwargs: key)
        message.reply.assert_called_once()
        text = message.reply.call_args[0][0]
        assert "summary_pending" in text
        assert "@alice" in text
