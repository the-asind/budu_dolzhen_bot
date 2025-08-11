import pytest
from unittest.mock import AsyncMock, patch

from bot.handlers.debt_handlers import handle_debt_message
from bot.core.debt_parser import DebtParseError


@pytest.mark.asyncio
async def test_invalid_debt_message_sends_help(model_message):
    msg = model_message(text="@bad")
    msg.reply = AsyncMock()
    bot = AsyncMock()
    service = AsyncMock()
    with patch(
        "bot.handlers.debt_handlers.DebtManager.process_message",
        AsyncMock(side_effect=DebtParseError("invalid_username_format")),
    ):
        await handle_debt_message(msg, bot, service, lambda k, **kwargs: k)
    msg.reply.assert_called_once_with("unknown_command")
