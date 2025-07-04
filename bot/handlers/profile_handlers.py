from typing import Callable

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from ..db.repositories import user_repo
from ..db.models import User as UserModel

from bot.keyboards.profile_kbs import get_settings_menu_kb, back_to_settings_kb
from bot.locales.main import get_user_language, get_localization

profile_router = Router(name="profile")


class ProfileSettings(StatesGroup):
    """FSM States for profile settings."""

    main = State()
    contact_info = State()
    reminders = State()
    trusted_users = State()


@profile_router.message(commands=["settings"])
async def settings_handler(message: Message, state: FSMContext):
    user_lang = await get_user_language(message.from_user.id, state)
    await message.answer(
        text=get_localization(user_lang).SETTINGS,
        reply_markup=get_settings_menu_kb(user_lang),
    )


@profile_router.callback_query(F.data == "set_contact")
async def set_contact_handler(callback: CallbackQuery, state: FSMContext):
    user_lang = await get_user_language(callback.from_user.id, state)
    await callback.message.edit_text(
        text=get_localization(user_lang).SET_CONTACT_PROMPT,
        reply_markup=back_to_settings_kb(user_lang),
    )
    # TODO: Implement FSM to wait for user's contact info


@profile_router.callback_query(F.data == "set_reminders")
async def set_reminders_handler(callback: CallbackQuery, state: FSMContext):
    user_lang = await get_user_language(callback.from_user.id, state)
    await callback.message.edit_text(
        text=get_localization(user_lang).COMING_SOON, # Placeholder
        reply_markup=back_to_settings_kb(user_lang),
    )
    # TODO: Implement reminder settings keyboard and logic


@profile_router.callback_query(F.data == "manage_trusted")
async def manage_trusted_handler(callback: CallbackQuery, state: FSMContext):
    user_lang = await get_user_language(callback.from_user.id, state)
    await callback.message.edit_text(
        text=get_localization(user_lang).COMING_SOON, # Placeholder
        reply_markup=back_to_settings_kb(user_lang),
    )
    # TODO: Implement trusted user management


@profile_router.callback_query(F.data == "back_to_settings")
async def back_to_settings_handler(callback: CallbackQuery, state: FSMContext):
    user_lang = await get_user_language(callback.from_user.id, state)
    await callback.message.edit_text(
        text=get_localization(user_lang).SETTINGS,
        reply_markup=get_settings_menu_kb(user_lang),
    )


@profile_router.message(ProfileSettings.contact_info)
async def handle_contact_info_input(
    message: Message, state: FSMContext, _: Callable, db_user: UserModel
):
    """
    Handles user input for contact information.
    """
    if not message.text:
        return

    await user_repo.update_user_contact(db_user.user_id, message.text)

    # TODO: i18n
    await message.answer(f"Ваши реквизиты обновлены: `{message.text}`")
    
    # Return to main settings menu
    await settings_handler(message, state) 