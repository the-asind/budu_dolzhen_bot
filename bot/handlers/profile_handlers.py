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

from ..db.repositories import UserRepository
from ..db.repositories import UserRepository
from ..db.models import User as UserModel

from bot.keyboards.profile_kbs import get_settings_menu_kb, back_to_settings_kb
from bot.locales.main import get_user_language, get_localization
from bot.utils.validators import (
    validate_username,
    is_valid_contact_info,
    validate_contact_info
)

user_repo = UserRepository()
profile_router = Router(name="profile")


class ProfileSettings(StatesGroup):
    """FSM States for profile settings."""

    main = State()
    contact_info = State()
    reminders = State()
    trusted_users = State()


@profile_router.message(Command("settings"))
async def settings_handler(message: Message, state: FSMContext):
    if message.from_user is None:
        return
    
    user_lang = await get_user_language(message.from_user.id, state)
    # Clear any existing FSM state and set to main
    await state.clear()
    await state.set_state(ProfileSettings.main)

    await message.answer(
        text=str(get_localization(user_lang).SETTINGS),
        reply_markup=get_settings_menu_kb(user_lang),
    )


@profile_router.callback_query(F.data == "set_contact")
async def set_contact_handler(callback: CallbackQuery, state: FSMContext):
    user_lang = await get_user_language(callback.from_user.id, state)
    message = callback.message
    if isinstance(message, Message):
        await message.edit_text(
        text=str(get_localization(user_lang).profile_contact_prompt),
        reply_markup=back_to_settings_kb(user_lang),
    )
    await state.set_state(ProfileSettings.contact_info)


@profile_router.message(ProfileSettings.contact_info)
async def handle_contact_info_input(
    message: Message, state: FSMContext, _: Callable, db_user: UserModel
):
    """
    Handles user input for contact information.
    """
    if message.from_user is None:
        return
    
    user_lang = await get_user_language(message.from_user.id, state)
    text = message.text or ""

    if not text.strip() or not is_valid_contact_info(text):
        await message.reply(str(get_localization(user_lang).profile_contact_invalid))
        return

    await user_repo.update_user_contact(db_user.user_id, text)
    await message.answer(str(get_localization(user_lang).profile_contact_saved))
    await state.clear()
    await settings_handler(message, state)


@profile_router.callback_query(F.data == "set_reminders")
async def set_reminders_handler(callback: CallbackQuery, state: FSMContext):
    user_lang = await get_user_language(callback.from_user.id, state)
    message = callback.message
    if isinstance(message, Message):
        await message.edit_text(
        text=str(get_localization(user_lang).reminder_settings_prompt),
        reply_markup=back_to_settings_kb(user_lang),
    )
        
    await state.set_state(ProfileSettings.reminders)


@profile_router.message(ProfileSettings.reminders)
async def handle_reminders_input(
    message: Message, state: FSMContext, _: Callable, db_user: UserModel
):
    """
    Handles user input for reminder settings.
    Expecting comma-separated days of month (1-31).
    """
    if message.from_user is None:
        return
    
    user_lang = await get_user_language(message.from_user.id, state)
    text = message.text or ""
    parts = [p.strip() for p in text.split(",") if p.strip()]
    days = []
    for part in parts:
        if not part.isdigit():
            await message.reply(str(get_localization(user_lang).reminder_invalid_day))
            return
        num = int(part)
        if num < 1 or num > 31:
            await message.reply(str(get_localization(user_lang).reminder_invalid_day))
            return
        days.append(str(num))
    # Save reminder settings as comma-separated string
    days_str = ",".join(days)
    await user_repo.update_user_reminders(db_user.user_id, days_str)
    # Acknowledge
    await message.answer(str(get_localization(user_lang).reminder_settings_saved))

    await state.clear()
    await settings_handler(message, state)


@profile_router.callback_query(F.data == "manage_trusted")
async def manage_trusted_handler(callback: CallbackQuery, state: FSMContext):
    user_lang = await get_user_language(callback.from_user.id, state)
    loc = get_localization(user_lang)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=str(getattr(loc, "TRUSTED_USER_ADD_PROMPT", "Add")),
                    callback_data="trusted_add",
                )
            ],
            [
                InlineKeyboardButton(
                    text=str(getattr(loc, "TRUSTED_USER_REMOVE_PROMPT", "Remove")),
                    callback_data="trusted_remove",
                )
            ],
            [
                InlineKeyboardButton(
                    text=str(getattr(loc, "TRUSTED_USERS_MENU", "Trusted Users")),
                    callback_data="trusted_list",
                )
            ],
            [
                InlineKeyboardButton(
                    text=str(getattr(loc, "GENERIC_BACK", "Back")),
                    callback_data="back_to_settings",
                )
            ],
        ]
    )
    message = callback.message
    if isinstance(message, Message):
        await message.edit_text(
        text=str(getattr(loc, "TRUSTED_USERS_MENU", "Trusted Users")),
        reply_markup=kb,
    )
    await state.set_state(ProfileSettings.trusted_users)
    await state.update_data(action=None)


@profile_router.callback_query(F.data == "trusted_add")
async def trusted_add_handler(callback: CallbackQuery, state: FSMContext):
    user_lang = await get_user_language(callback.from_user.id, state)
    loc = get_localization(user_lang)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=loc.generic_cancel, callback_data="manage_trusted")],
    ])
    message = callback.message
    if isinstance(message, Message):
        await message.edit_text(
        text=str(getattr(loc, "trusted_user_add_prompt", "Add trusted user")),
        reply_markup=kb,
    )
    await state.set_state(ProfileSettings.trusted_users)
    await state.update_data(action="add")


@profile_router.callback_query(F.data == "trusted_remove")
async def trusted_remove_handler(callback: CallbackQuery, state: FSMContext):
    user_lang = await get_user_language(callback.from_user.id, state)
    loc = get_localization(user_lang)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=loc.generic_cancel, callback_data="manage_trusted")],
    ])
    message = callback.message
    if isinstance(message, Message):
        await message.edit_text(
        text=str(getattr(loc, "trusted_user_remove_prompt", "Remove trusted user")),
        reply_markup=kb,
    )
    await state.set_state(ProfileSettings.trusted_users)
    await state.update_data(action="remove")


@profile_router.callback_query(F.data == "trusted_list")
async def trusted_list_handler(
    callback: CallbackQuery, state: FSMContext, db_user: UserModel
):
    user_lang = await get_user_language(callback.from_user.id, state)
    loc = get_localization(user_lang)
    trusted = await user_repo.list_trusted(db_user.user_id)
    if not trusted:
        text = str(getattr(loc, "trusted_user_list_empty", "No trusted users"))
    else:
        lines = "\n".join(f"- {u}" for u in trusted)
        text = f"{str(getattr(loc, 'trusted_user_list_title', 'Trusted list'))}\n{lines}"
    message = callback.message
    if isinstance(message, Message):
        await message.edit_text(
        text=text,
        reply_markup=back_to_settings_kb(user_lang),
    )
    await state.clear()


@profile_router.message(ProfileSettings.trusted_users)
async def handle_trusted_input(
    message: Message, state: FSMContext, _: Callable, db_user: UserModel
):
    """
    Handles user input for adding or removing trusted users.
    """
    if message.from_user is None:
        return
    
    user_lang = await get_user_language(message.from_user.id, state)
    loc = get_localization(user_lang)
    data = await state.get_data()
    action = data.get("action")
    text = message.text or ""
    
    try:
        username = validate_username(text.strip())
    except ValueError:
        await message.reply(loc.error_validation.format(details=loc.trusted_user_add_prompt))
        return

    if action == "add":
        exists = await user_repo.trusts(db_user.user_id, username)
        if exists:
            await message.answer(str(getattr(loc, "trusted_user_add_exists", "{username} is already trusted!")).format(username=username))
        else:
            await user_repo.add_trust(db_user.user_id, username)
            await message.answer(str(getattr(loc, "trusted_user_add_success", "Added {username} to trusted users!")).format(username=username))
    elif action == "remove":
        exists = await user_repo.trusts(db_user.user_id, username)
        if not exists:
            await message.answer(str(getattr(loc, "trusted_user_remove_not_found", "User {username} not found")).format(username=username))
        else:
            await user_repo.remove_trust(db_user.user_id, username)
            await message.answer(str(getattr(loc, "trusted_user_remove_success", "Removed {username} from trusted users!")).format(username=username))
    else:
        # Unknown action, cancel
        await message.reply(str(getattr(loc, "fsm_invalid_state", "Invalid state.")))

    await state.clear()


@profile_router.callback_query(F.data == "back_to_settings")
async def back_to_settings_handler(callback: CallbackQuery, state: FSMContext):
    user_lang = await get_user_language(callback.from_user.id, state)
    await state.clear()
    await state.set_state(ProfileSettings.main)

    message = callback.message
    if isinstance(message, Message):
        await message.edit_text(
            text=get_localization(user_lang).SETTINGS,
            reply_markup=get_settings_menu_kb(user_lang),
        )
