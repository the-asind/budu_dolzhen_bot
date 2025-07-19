import pytest
from unittest.mock import AsyncMock, patch

from bot.handlers.debt_handlers import handle_debt_message
from bot.db.models import Debt


@pytest.mark.asyncio
async def test_notifications_sent(model_message, model_user, model_chat):
    message = model_message(
        text="@user1 100", from_user=model_user(), chat=model_chat()
    )
    message.reply = AsyncMock()
    with patch("bot.handlers.debt_handlers.DebtManager") as dm_cls, patch(
        "bot.handlers.debt_handlers.user_repo"
    ) as repo:
        notif = AsyncMock()
        debt = Debt(
            debt_id=1,
            creditor_id=1,
            debtor_id=2,
            amount=100,
            description="",
            status="pending",
        )
        dm = AsyncMock()
        dm.process_message.return_value = [debt]
        dm_cls.return_value = dm
        repo.get_by_username = AsyncMock(return_value=model_user(id=1))
        repo.get_by_id = AsyncMock(return_value=model_user(id=2))
        notif.send_debt_confirmation_request = AsyncMock()

        await handle_debt_message(
            message, AsyncMock(), notif, lambda key, **kwargs: key
        )

        notif.send_debt_confirmation_request.assert_called_once()
        message.reply.assert_called_with("debts_registered")
        
        
@pytest.mark.asyncio
async def test_debt_confirmation_localized(mock_aiogram_bot):
    service = NotificationService(mock_aiogram_bot)
    service.send_message = AsyncMock(return_value=True)

    creditor = User(user_id=1, username="cred", first_name="Cred", language_code="ru")
    debtor = User(user_id=2, username="deb", first_name="Deb", language_code="ru")
    debt = Debt(debt_id=10, creditor_id=1, debtor_id=2, amount=15000, description="обед", status="pending")

    await service.send_debt_confirmation_request(debt, creditor, debtor)

    service.send_message.assert_called_once()
    args, _ = service.send_message.call_args
    assert args[0] == debtor.user_id
    assert "cred" in args[1]
    assert "150" in args[1]
    assert "обед" in args[1]