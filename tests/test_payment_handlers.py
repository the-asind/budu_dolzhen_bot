import pytest
from unittest.mock import AsyncMock, patch

from bot.handlers.payment_handlers import handle_pay_command, handle_payment_callback
from bot.handlers.debt_handlers import router as debt_router
from bot.keyboards.debt_kbs import encode_callback_data
from tests.conftest import make_mutable_callback_query


@pytest.mark.asyncio
async def test_pay_command_success(model_message):
    msg = model_message(text="/pay @creditor 10")
    msg.reply = AsyncMock()
    service = AsyncMock()
    service.send_payment_confirmation_request = AsyncMock()
    with patch("bot.handlers.payment_handlers.payment_manager") as mock_mgr, patch(
        "bot.handlers.payment_handlers.UserRepository.get_by_username",
        AsyncMock(return_value=type("U", (), {"user_id": 1, "username": "creditor"})()),
    ), patch(
        "bot.handlers.payment_handlers.DebtRepository.list_active_between",
        AsyncMock(return_value=[type("D", (), {"debt_id": 1})()]),
    ), patch(
        "bot.handlers.payment_handlers._",
        lambda key, **kwargs: key,
    ):
        mock_mgr.process_payment = AsyncMock(return_value=type("P", (), {"payment_id": 5})())
        await handle_pay_command(msg, service, lambda key, **kwargs: key)
        mock_mgr.process_payment.assert_called_once()
        service.send_payment_confirmation_request.assert_called_once()
        msg.reply.assert_called_once_with("payment_registered")


@pytest.mark.asyncio
async def test_pay_command_error(model_message):
    msg = model_message(text="/pay @creditor 10")
    msg.reply = AsyncMock()
    service = AsyncMock()
    service.send_payment_confirmation_request = AsyncMock()
    with patch("bot.handlers.payment_handlers.payment_manager") as mock_mgr, patch(
        "bot.handlers.payment_handlers.UserRepository.get_by_username",
        AsyncMock(return_value=type("U", (), {"user_id": 1, "username": "creditor"})()),
    ), patch(
        "bot.handlers.payment_handlers.DebtRepository.list_active_between",
        AsyncMock(return_value=[type("D", (), {"debt_id": 1})()]),
    ), patch(
        "bot.handlers.payment_handlers._",
        lambda key, **kwargs: key,
    ):
        mock_mgr.process_payment = AsyncMock(side_effect=ValueError("oops"))
        await handle_pay_command(msg, service, lambda key, **kwargs: key)
        mock_mgr.process_payment.assert_called_once()
        service.send_payment_confirmation_request.assert_not_called()
        msg.reply.assert_called_once_with("payment_processing_error")


@pytest.mark.asyncio
async def test_pay_command_invalid_format(model_message):
    msg = model_message(text="/pay @creditor")
    msg.reply = AsyncMock()
    service = AsyncMock()
    service.send_payment_confirmation_request = AsyncMock()
    await handle_pay_command(msg, service, lambda key, **kwargs: key)
    msg.reply.assert_called_once_with("invalid_pay_command_format")


@pytest.mark.asyncio
async def test_payment_callback_approve(model_user, mock_notification_service):
    cb = make_mutable_callback_query(
        from_user=model_user(id=1, username="cred"),
        data=encode_callback_data("payment_approve", 1, payment_id=5),
    )
    with patch(
        "bot.handlers.payment_handlers.DebtRepository.get",
        AsyncMock(return_value=type("D", (), {"creditor_id": 1, "debtor_id": 2})()),
    ), patch(
        "bot.handlers.payment_handlers.UserRepository.get_by_id",
        AsyncMock(return_value=type("U", (), {"user_id": 2, "username": "deb"})()),
    ), patch(
        "bot.handlers.payment_handlers.payment_manager.confirm_payment",
        AsyncMock(return_value=type("P", (), {"amount": 100})()),
    ), patch(
        "bot.handlers.payment_handlers._",
        lambda key, **kwargs: key,
    ):
        await handle_payment_callback(cb, mock_notification_service, lambda k, **_: k)

    cb.message.edit_text.assert_called_once_with("payment_confirm_approved")
    mock_notification_service.send_message.assert_called_once()


@pytest.mark.asyncio
async def test_payment_callback_reject(model_user, mock_notification_service):
    cb = make_mutable_callback_query(
        from_user=model_user(id=1, username="cred"),
        data=encode_callback_data("payment_reject", 1, payment_id=5),
    )
    with patch(
        "bot.handlers.payment_handlers.DebtRepository.get",
        AsyncMock(return_value=type("D", (), {"creditor_id": 1, "debtor_id": 2})()),
    ), patch(
        "bot.handlers.payment_handlers.UserRepository.get_by_id",
        AsyncMock(return_value=type("U", (), {"user_id": 2, "username": "deb"})()),
    ), patch(
        "bot.handlers.payment_handlers.payment_manager.reject_payment",
        AsyncMock(return_value=type("P", (), {"amount": 100})()),
    ), patch(
        "bot.handlers.payment_handlers._",
        lambda key, **kwargs: key,
    ):
        await handle_payment_callback(cb, mock_notification_service, lambda k, **_: k)

    cb.message.edit_text.assert_called_once_with("payment_confirm_declined")
    mock_notification_service.send_message.assert_called_once()


@pytest.mark.asyncio
async def test_debt_handler_filter_excludes_payment_callback(model_user):
    cb = make_mutable_callback_query(
        from_user=model_user(id=1, username="cred"),
        data=encode_callback_data("payment_approve", 1, payment_id=5),
    )
    filter_fn = debt_router.callback_query.handlers[0].filters[0].callback
    assert filter_fn(cb) is False
