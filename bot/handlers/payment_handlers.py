import re
from decimal import Decimal
from typing import Callable

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from ..core.payment_manager import PaymentManager

router = Router()
payment_manager = PaymentManager()

# Command format: /pay <debt_id> <amount>
PAY_COMMAND_RE = re.compile(r"/pay\s+(\d+)\s+([\d.,]+)")


@router.message(Command("pay"))
async def handle_pay_command(message: Message, _: Callable) -> None:
    """Process the /pay command and register a payment."""
    if not message.text or not message.from_user:
        return

    match = PAY_COMMAND_RE.match(message.text)
    if not match:
        await message.reply(_("invalid_pay_command_format", command=html.escape("/pay <ID долга> <сумма>")))
        return

    debt_id_str, amount_str = match.groups()
    debt_id = int(debt_id_str)
    amount_in_cents = int(Decimal(amount_str.replace(",", ".")) * 100)

    try:
        await payment_manager.process_payment(debt_id=debt_id, amount_in_cents=amount_in_cents)
    except Exception as exc:  # noqa: BLE001 - surface error to user
        await message.reply(_("payment_processing_error", reason=str(exc)))
        return

    await message.reply(_("payment_registered"))