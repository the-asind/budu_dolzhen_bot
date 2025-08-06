import logging
from typing import Callable, Dict, List
from collections import defaultdict

from aiogram import Bot, Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery

from ..core.debt_manager import DebtManager
from ..core.notification_service import NotificationService
from ..db.repositories import DebtRepository, UserRepository
from ..utils.formatters import format_amount
from ..keyboards.debt_kbs import decode_callback_data

router = Router()
user_repo = UserRepository()
logger = logging.getLogger(__name__)


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
            await bot.delete_message(chat_id=message.chat.id, message_id=message.message_id)
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
        creditor = await user_repo.get_by_username((message.from_user.username or "").lower())
        for debt in result:
            debtor = await user_repo.get_by_id(debt.debtor_id)
            if debtor and creditor:
                await notification_service.send_debt_confirmation_request(debt, creditor, debtor)
    else:
        await message.reply(_("error_in_message"))


@router.message(Command("summary"))
async def handle_summary_command(message: Message, _: Callable) -> None:
    """Send a quick overview of a user's active debts and credits."""
    if not message.from_user:
        return

    debts = await DebtRepository.list_active_by_user(message.from_user.id)
    if not debts:
        await message.reply(_("summary_none"))
        return

    owes: Dict[str, int] = defaultdict(int)
    owed: Dict[str, int] = defaultdict(int)

    for debt in debts:
        if debt.debtor_id == message.from_user.id:
            other = await user_repo.get_by_id(debt.creditor_id)
            if other and other.username:
                owes["@" + other.username] += debt.amount
            else:
                owes[str(debt.creditor_id)] += debt.amount
        else:
            other = await user_repo.get_by_id(debt.debtor_id)
            if other and other.username:
                owed["@" + other.username] += debt.amount
            else:
                owed[str(debt.debtor_id)] += debt.amount

    lines: List[str] = [_("summary_header")]
    if owes:
        lines.append(_("summary_you_owe"))
        for user, amount in owes.items():
            lines.append(f"- {user} {format_amount(amount)}")
    if owed:
        lines.append("")
        lines.append(_("summary_owed_to_you"))
        for user, amount in owed.items():
            lines.append(f"- {user} {format_amount(amount)}")

    await message.reply("\n".join(lines))


@router.callback_query()
async def handle_debt_callback(callback: CallbackQuery, _: Callable) -> None:
    """Process Agree/Decline actions from debt confirmation keyboards."""
    if not callback.data:
        return

    payload = decode_callback_data(callback.data)
    action = payload.get("action")
    debt_id = payload.get("debt_id")

    if action not in {"debt_agree", "debt_decline"} or debt_id is None:
        return

    try:
        if action == "debt_agree":
            debtor_username = callback.from_user.username or ""
            await DebtManager.confirm_debt(debt_id, debtor_username=debtor_username)
            text = _("debt_confirmed_success", debt_id=debt_id)
        else:
            debt = await DebtRepository.get(debt_id)
            if debt is None or debt.debtor_id != callback.from_user.id:
                await callback.answer(_("debt_confirmation_unauthorized"), show_alert=True)
                return
            await DebtRepository.update_status(debt_id, "rejected")
            text = _("debt_declined_success", debt_id=debt_id)

        await callback.message.edit_text(text)
        await callback.answer()
    except ValueError as exc:  # noqa: BLE001
        logger.warning("Debt callback failed: %s", exc)
        await callback.answer(_("debt_not_found_error"), show_alert=True)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected error processing debt callback: %s", exc)
        await callback.answer(_("error_generic"), show_alert=True)
