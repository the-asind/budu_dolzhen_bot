from typing import Callable
from aiogram import Bot, Router, F
from aiogram.types import Message

from ..core.debt_manager import DebtManager
from ..core.notification_service import NotificationService
from ..db.repositories import UserRepository

router = Router()
user_repo = UserRepository()


@router.message(F.text & F.text.startswith("@"))
async def handle_debt_message(
    message: Message,
    bot: Bot,
    notification_service: NotificationService,
    _: Callable,
):
    """
    Handler for messages that appear to be debt registrations.
    Context-aware behavior for private and group chats.
    """
    if not message.text or not message.from_user:
        return

    chat_type = message.chat.type

    if chat_type in ("group", "supergroup"):
        try:
            member = await bot.get_chat_member(message.chat.id, message.from_user.id)
            if member.status not in ("administrator", "creator"):
                await message.reply(_("debt_group_only_admins"))
                return
        except Exception:
            await message.reply(_("debt_group_admin_check_failed"))
            return

        try:
            await bot.delete_message(
                chat_id=message.chat.id, message_id=message.message_id
            )
        except Exception:
            pass

        try:
            await bot.send_message(
                chat_id=message.from_user.id,
                text=_("debt_group_dm_instruction"),
            )
        except Exception:
            await message.reply(_("debt_group_start_bot_first"))
        return

    text = message.text.strip()

    debt_manager = DebtManager()

    result = await debt_manager.process_message(
        message=text,
        author_username=message.from_user.username or "",
    )

    if result:
        await message.reply(_("debts_registered"))
        creditor = await user_repo.get_by_username(
            (message.from_user.username or "").lower()
        )
        for debt in result:
            debtor = await user_repo.get_by_id(debt.debtor_id)
            if debtor and creditor:
                await notification_service.send_debt_confirmation_request(
                    debt, creditor, debtor
                )
    else:
        await message.reply(_("error_in_message"))
