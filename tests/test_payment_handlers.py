import pytest
from unittest.mock import AsyncMock, patch

from bot.handlers.payment_handlers import handle_pay_command


@pytest.mark.asyncio
async def test_pay_command_success(model_message):
    msg = model_message(text="/pay 1 10")
    msg.reply = AsyncMock()
    with patch("bot.handlers.payment_handlers.payment_manager") as mock_mgr, patch(
        "bot.handlers.payment_handlers._", lambda key, **kwargs: key
    ):
        mock_mgr.process_payment = AsyncMock()
        await handle_pay_command(msg, lambda key, **kwargs: key)
        mock_mgr.process_payment.assert_called_once()
        msg.reply.assert_called_once_with("payment_registered")


@pytest.mark.asyncio
async def test_pay_command_error(model_message):
    msg = model_message(text="/pay 1 10")
    msg.reply = AsyncMock()
    with patch("bot.handlers.payment_handlers.payment_manager") as mock_mgr, patch(
        "bot.handlers.payment_handlers._", lambda key, **kwargs: key
    ):
        mock_mgr.process_payment = AsyncMock(side_effect=ValueError("oops"))
        await handle_pay_command(msg, lambda key, **kwargs: key)
        mock_mgr.process_payment.assert_called_once()
        msg.reply.assert_called_once_with("payment_processing_error")

@pytest.mark.asyncio
async def test_pay_command_invalid_format(model_message):
    msg = model_message(text="/pay 1")
    msg.reply = AsyncMock()
    await handle_pay_command(msg, lambda key, **kwargs: key)
    msg.reply.assert_called_once_with("invalid_pay_command_format")
