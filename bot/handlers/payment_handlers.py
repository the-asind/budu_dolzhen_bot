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


@router.message(Command(commands=["pay"]))
async def handle_pay_command(message: Message, _: Callable):
    """
    Handler for the /pay command to record a payment against a debt.
    """
    if not message.text or not message.from_user:
        return

    match = PAY_COMMAND_RE.match(message.text)
    if not match:
        await message.reply(
            _("invalid_pay_command_format", command="/pay <ID долга> <сумма>")
        )
        return

    debt_id_str, amount_str = match.groups()
    debt_id = int(debt_id_str)
    amount_in_cents = int(Decimal(amount_str.replace(",", ".")) * 100)

    # In a real app, we'd need more logic here:
    # 1. Verify that the user sending the command is the debtor of this debt.
    # 2. Handle partial or full payments.
    # 3. Trigger confirmation workflow with the creditor.
    await payment_manager.process_payment(
        debt_id=debt_id, amount_in_cents=amount_in_cents
    )

    await message.reply(_("payment_registered")) 