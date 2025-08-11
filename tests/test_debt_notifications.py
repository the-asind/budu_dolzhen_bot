import pytest
from unittest.mock import AsyncMock, patch

from bot.db.models import User

from bot.handlers.debt_handlers import handle_debt_message
from bot.db.models import Debt
from bot.core.notification_service import NotificationService

@pytest.mark.asyncio
async def test_debt_confirmation_localized(mock_aiogram_bot):
    service = NotificationService(mock_aiogram_bot)
    service.send_message = AsyncMock(return_value=True)

    creditor = User(user_id=1, username="cred", first_name="Cred", language_code="ru")
    debtor = User(user_id=2, username="deb", first_name="Deb", language_code="ru")
    debt = Debt(
        debt_id=10,
        creditor_id=1,
        debtor_id=2,
        amount=15000,
        description="обед",
        status="pending",
    )

    await service.send_debt_confirmation_request(debt, creditor, debtor)

    service.send_message.assert_called_once()
    args, _ = service.send_message.call_args
    assert args[0] == debtor.user_id
    assert "cred" in args[1]
    assert "150" in args[1]
    assert "обед" in args[1]