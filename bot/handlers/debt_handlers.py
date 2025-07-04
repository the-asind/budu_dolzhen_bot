from typing import Callable
from aiogram import Bot, Router, F
from aiogram.types import Message

from ..core.debt_manager import DebtManager
from ..core.debt_parser import DebtParser
from ..core.notification_service import NotificationService

router = Router()


@router.message(F.text & F.text.startswith("@"))
async def handle_debt_message(
    message: Message,
    bot: Bot,
    notification_service: NotificationService,
    _: Callable,
):
    """
    Handler for messages that appear to be debt registrations.
    """
    if not message.text or not message.from_user:
        return

    # In a real app, you might inject this via a middleware or a proper DI container
    debt_manager = DebtManager(DebtParser(), notification_service)

    result = await debt_manager.process_debt_message(
        message_text=message.text,
        creditor_tg_id=message.from_user.id,
        _=_,
    )

    if result.errors:
        errors = "\n".join(result.errors)
        await message.reply(_("error_in_message", errors=errors))
    else:
        await message.reply(_("debts_registered")) 