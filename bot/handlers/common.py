from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from typing import Callable

from ..db.repositories import UserRepository

router = Router()
user_repo = UserRepository()


@router.message(Command("start"))
async def handle_start_command(message: Message, _: Callable):
    """
    Handler for the /start command.
    Greets the user and registers them in the system.
    Implements an enhanced onboarding flow with step-by-step guidance,
    interactive examples, and contextual resource links.
    """
    user = message.from_user
    if not user:
        return

    db_user = await user_repo.get_or_create_user(
        user_id=user.id,
        username=user.username or f"user_{user.id}",
        first_name=user.first_name or (user.username or str(user.id)),
        language_code=user.language_code or "en",
    )

    chat_type = message.chat.type

    if chat_type == "private":
        # Private chat onboarding: detailed step-by-step in a single message
        onboarding_text = (
            f"{_('start_welcome')}\n\n"
            f"{_('onboarding_private_step1')}\n\n"
            f"{_('onboarding_private_step2')}\n\n"
            f"{_('onboarding_private_step3')}\n\n"
            f"{_('onboarding_private_example')}"
        )
        await message.answer(onboarding_text)
    else:
        # Group chat onboarding: concise overview and privacy notice in a single message
        group_onboarding_text = (
            f"{_('start_welcome_group')}\n\n"
            f"{_('onboarding_group_step1')}\n\n"
            f"{_('onboarding_group_step2')}"
        )
        await message.answer(group_onboarding_text)

    resources_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=_("btn_github"), url="https://github.com/the-asind/budu_dolzhen_bot"),
            ],
        ]
    )
    await message.answer(_("onboarding_resources"), reply_markup=resources_kb)


@router.message(Command("help"))
async def handle_help_command(message: Message, _: Callable):
    """
    Handler for the /help command.
    Provides a detailed help message with command-specific instructions,
    FAQ, troubleshooting sections, inline hints, and resource links.
    """
    help_text = (
        f"{_('help_intro')}\n\n"
        f"{_('help_commands')}\n\n"
        f"{_('help_faq')}\n\n"
        f"{_('help_troubleshooting')}\n\n"
        f"{_('help_hints')}"
    )
    await message.answer(help_text)

    help_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=_("btn_github"), url="https://github.com/the-asind/budu_dolzhen_bot"),
            ],
        ]
    )
    await message.answer(_("help_resources"), reply_markup=help_kb)
