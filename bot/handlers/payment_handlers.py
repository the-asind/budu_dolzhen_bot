import re
import html
from decimal import Decimal
from typing import Callable

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery

from ..core.notification_service import NotificationService
from ..core.payment_manager import PaymentManager
from ..db.repositories import DebtRepository, UserRepository
from ..keyboards.debt_kbs import decode_callback_data
from ..utils.formatters import format_amount

router = Router()
payment_manager = PaymentManager()

# Command format: /pay <creditor_username> <amount>
PAY_COMMAND_RE = re.compile(r"/pay\s+@?([A-Za-z0-9_]{5,})\s+([\d.,]+)")


@router.message(Command("pay"))
async def handle_pay_command(message: Message, notification_service: NotificationService, _: Callable) -> None:
    """Process the /pay command and register a payment."""
    if not message.text or not message.from_user:
        return

    match = PAY_COMMAND_RE.match(message.text)
    if not match:
        await message.reply(
            _(
                "invalid_pay_command_format",
                command=html.escape("/pay @username <amount>"),
            )
        )
        return

    username, amount_str = match.groups()
    username = username.lower()
    amount_in_cents = int(Decimal(amount_str.replace(",", ".")) * 100)

    creditor = await UserRepository.get_by_username(username)
    if creditor is None:
        await message.reply(_("user_mention_not_registered", username=username))
        return

    debts = await DebtRepository.list_active_between(creditor.user_id, message.from_user.id)
    if not debts:
        await message.reply(_("payment_debt_not_found"))
        return
    debt_id = debts[0].debt_id

    try:
        payment = await payment_manager.process_payment(debt_id=debt_id, amount_in_cents=amount_in_cents)
    except Exception as exc:  # noqa: BLE001 - surface error to user
        reason = str(exc)
        if reason in {
            "payment_amount_positive",
            "payment_debt_not_found",
            "payment_invalid_status",
            "payment_exceeds_remaining",
            "payment_not_found",
        }:
            await message.reply(_(reason))
        else:
            await message.reply(_("payment_processing_error", reason=reason))
        return

    await notification_service.send_payment_confirmation_request(
        payment.payment_id,
        debt_id,
        amount_in_cents,
        creditor,
        message.from_user,
    )

    await message.reply(_("payment_registered"))


@router.callback_query(
    lambda c: c.data and decode_callback_data(c.data).get("action") in {"payment_approve", "payment_reject"}
)
async def handle_payment_callback(
    callback: CallbackQuery, notification_service: NotificationService, _: Callable
) -> None:
    """Handle payment confirmation callbacks from the creditor."""
    if not callback.data:
        return

    payload = decode_callback_data(callback.data)
    action = payload.get("action")
    payment_id = payload.get("payment_id")
    debt_id = payload.get("debt_id")

    if payment_id is None or debt_id is None:
        return

    debt = await DebtRepository.get(debt_id)
    if debt is None or debt.creditor_id != callback.from_user.id:
        await callback.answer(_("payment_confirmation_unauthorized"), show_alert=True)
        return

    payer = await UserRepository.get_by_id(debt.debtor_id)

    try:
        if action == "payment_approve":
            payment = await payment_manager.confirm_payment(payment_id)
            await callback.message.edit_text(_("payment_confirm_approved", amount=format_amount(payment.amount)))
            if payer:
                await notification_service.send_message(
                    payer.user_id,
                    _(
                        "payment_confirmed_debtor_notice",
                        creditor=f"@{callback.from_user.username}",
                        amount=format_amount(payment.amount),
                    ),
                )
        else:
            payment = await payment_manager.reject_payment(payment_id)
            await callback.message.edit_text(_("payment_confirm_declined", amount=format_amount(payment.amount)))
            if payer:
                await notification_service.send_message(
                    payer.user_id,
                    _(
                        "payment_declined_debtor_notice",
                        creditor=f"@{callback.from_user.username}",
                        amount=format_amount(payment.amount),
                    ),
                )
        await callback.answer()
    except Exception:  # noqa: BLE001
        await callback.answer(_("error_generic"), show_alert=True)
