import json
from unittest.mock import AsyncMock, patch

import pytest

from bot.handlers.debt_handlers import handle_debt_callback
from bot.db.models import Debt, User


pytestmark = pytest.mark.asyncio


async def test_notify_creditor_on_accept(model_callback_query):
    cb = model_callback_query(data=json.dumps({"action": "debt_agree", "debt_id": 1}))
    cb.message.edit_text = AsyncMock()
    object.__setattr__(cb, "answer", AsyncMock())
    service = AsyncMock()
    service.send_message = AsyncMock()
    debt = Debt(debt_id=1, creditor_id=1, debtor_id=cb.from_user.id, amount=100, description="", status="active")
    with patch("bot.handlers.debt_handlers.DebtManager.confirm_debt", AsyncMock(return_value=debt)), patch(
        "bot.handlers.debt_handlers.UserRepository.get_by_id",
        AsyncMock(return_value=User(user_id=1, username="creditor", first_name="c")),
    ), patch("bot.handlers.debt_handlers._", lambda k, **kwargs: k), patch(
        "bot.handlers.debt_handlers.format_amount", lambda x: str(x)
    ):
        await handle_debt_callback(cb, service, lambda key, **kwargs: key)
        service.send_message.assert_called_once()


async def test_notify_creditor_on_decline(model_callback_query):
    cb = model_callback_query(data=json.dumps({"action": "debt_decline", "debt_id": 1}))
    cb.message.edit_text = AsyncMock()
    object.__setattr__(cb, "answer", AsyncMock())
    service = AsyncMock()
    service.send_message = AsyncMock()
    debt = Debt(debt_id=1, creditor_id=1, debtor_id=cb.from_user.id, amount=100, description="", status="pending")
    with patch("bot.handlers.debt_handlers.DebtRepository.get", AsyncMock(return_value=debt)), patch(
        "bot.handlers.debt_handlers.DebtRepository.update_status", AsyncMock()
    ), patch(
        "bot.handlers.debt_handlers.UserRepository.get_by_id",
        AsyncMock(return_value=User(user_id=1, username="creditor", first_name="c")),
    ), patch(
        "bot.handlers.debt_handlers._", lambda k, **kwargs: k
    ), patch(
        "bot.handlers.debt_handlers.format_amount", lambda x: str(x)
    ):
        await handle_debt_callback(cb, service, lambda key, **kwargs: key)
        service.send_message.assert_called_once()
