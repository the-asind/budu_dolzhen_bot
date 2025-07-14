from typing import Callable, Dict, List, Optional

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from ..db.repositories import UserRepository
from ..db.models import User as UserModel
from ..locales import LOCALES_DIR

language_router = Router(name="language")

AVAILABLE_LANGUAGES = {
    "en": "🇺🇸 English",
    "ru": "🇷🇺 Русский"
}

def get_available_languages() -> Dict[str, str]:
    """Get available languages from locale files."""
    available = {}
    for locale_file in LOCALES_DIR.glob("*.json"):
        lang_code = locale_file.stem
        if lang_code == "en":
            available[lang_code] = "🇺🇸 English"
        elif lang_code == "ru":
            available[lang_code] = "🇷🇺 Русский"
        else:
            available[lang_code] = f"🌐 {lang_code.upper()}"
    return available

def create_language_keyboard(current_lang: Optional[str] = None) -> InlineKeyboardMarkup:
    """Create inline keyboard for language selection."""
    buttons = []
    available_langs = get_available_languages()
    
    for lang_code, lang_name in available_langs.items():
        display_name = f"✅ {lang_name}" if lang_code == current_lang else lang_name
        button = InlineKeyboardButton(
            text=display_name,
            callback_data=f"set_lang_{lang_code}"
        )
        buttons.append([button])
    
    buttons.append([
        InlineKeyboardButton(
            text="⬅️ Back to Settings",
            callback_data="back_to_settings"
        )
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

@language_router.message(Command("language"))
async def language_command_handler(
    message: Message, 
    state: FSMContext, 
    user_repo: UserRepository,
    _: Callable = None,
    db_user: Optional[UserModel] = None,
):
    """Handle /language command to show language selection menu."""
    current_lang = db_user.language_code if db_user else "ru"
    
    if current_lang == "en":
        text = "🌐 Choose your language:\n\nSelect your preferred language for bot interface."
    else:
        text = "🌐 Выберите язык:\n\nВыберите предпочитаемый язык интерфейса бота."
    
    keyboard = create_language_keyboard(current_lang)
    
    await message.answer(
        text=text,
        reply_markup=keyboard
    )

@language_router.callback_query(F.data.startswith("set_lang_"))
async def language_selection_handler(
    callback: CallbackQuery,
    state: FSMContext,
    user_repo: UserRepository,
    _: Callable = None,
    db_user: Optional[UserModel] = None,
):
    """Handle language selection from inline keyboard."""
    if not callback.data:
        return
    
    # Extract language code from callback data
    lang_code = callback.data.replace("set_lang_", "")
    
    available_langs = get_available_languages()
    if lang_code not in available_langs:
        await callback.answer("❌ Invalid language selection", show_alert=True)
        return
    
    if db_user:
        try:
            await user_repo.update_user_language(db_user.user_id, lang_code)
            
            if lang_code == "en":
                confirmation_text = f"✅ Language changed to English!\n\nAll bot messages will now be displayed in English."
                success_alert = "Language updated successfully!"
            else:
                confirmation_text = f"✅ Язык изменен на русский!\n\nВсе сообщения бота теперь будут отображаться на русском языке."
                success_alert = "Язык успешно обновлен!"
            
            message = callback.message
            if isinstance(message, Message):
                await message.edit_text(
                text=confirmation_text,
                reply_markup=create_back_to_settings_keyboard(lang_code)
            )
            
            await callback.answer(success_alert, show_alert=False)
            
            await state.update_data(user_language=lang_code)
            
        except Exception as e:
            error_text = "❌ Failed to update language" if lang_code == "en" else "❌ Не удалось обновить язык"
            await callback.answer(error_text, show_alert=True)
    else:
        error_text = "❌ User not found" if lang_code == "en" else "❌ Пользователь не найден"
        await callback.answer(error_text, show_alert=True)

def create_back_to_settings_keyboard(lang_code: str) -> InlineKeyboardMarkup:
    """Create keyboard with back to settings button."""
    if lang_code == "en":
        back_text = "⬅️ Back to Settings"
    else:
        back_text = "⬅️ Назад к настройкам"
    
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=back_text, callback_data="back_to_settings")]
    ])

@language_router.callback_query(F.data == "language_settings")
async def language_settings_from_profile(
    callback: CallbackQuery,
    state: FSMContext,
    user_repo: UserRepository,
    _: Callable = None,
    db_user: Optional[UserModel] = None,
):
    """Handle language settings access from profile menu."""
    current_lang = db_user.language_code if db_user else "ru"
    
    if current_lang == "en":
        text = "🌐 Language Settings\n\nCurrent language: {}\n\nSelect a new language:".format(
            AVAILABLE_LANGUAGES.get(current_lang, current_lang)
        )
    else:
        text = "🌐 Настройки языка\n\nТекущий язык: {}\n\nВыберите новый язык:".format(
            AVAILABLE_LANGUAGES.get(current_lang, current_lang)
        )
    
    keyboard = create_language_keyboard(current_lang)
    
    message = callback.message
    if isinstance(message, Message):
        await message.edit_text(
        text=text,
        reply_markup=keyboard
    )

async def detect_user_language_from_telegram(user_id: int, telegram_lang_code: Optional[str], user_repo: UserRepository) -> Optional[str]:
    """
    Detect and update user language based on Telegram settings.
    This function can be called from middleware when user language changes.
    """
    if not telegram_lang_code:
        return None
    
    lang_mapping = {
        "en": "en",
        "ru": "ru",
        "uk": "ru",
        "be": "ru",
        "kz": "ru",
    }
    
    base_lang = telegram_lang_code.split("-")[0].lower()
    mapped_lang = lang_mapping.get(base_lang)
    
    if mapped_lang and mapped_lang in get_available_languages():
        try:
            await user_repo.update_user_language(user_id, mapped_lang)
            return mapped_lang
        except Exception:
            pass
    
    return None

async def get_user_language_preference(user_id: int, user_repo: UserRepository) -> str:
    """Get user's language preference from database with fallback."""
    try:
        user = await user_repo.get_by_id(user_id)
        if user and user.language_code:
            return user.language_code
    except Exception:
        pass
    
    # Default fallback
    return "ru"

def create_language_menu_button(lang_code: str) -> InlineKeyboardButton:
    """Create language menu button for profile settings."""
    if lang_code == "en":
        text = "🌐 Language"
    else:
        text = "🌐 Язык"
    
    return InlineKeyboardButton(text=text, callback_data="language_settings")

async def apply_language_change(user_id: int, new_lang: str, user_repo: UserRepository) -> bool:
    """
    Apply language change immediately and return success status.
    This ensures the change takes effect without requiring bot restart.
    """
    try:
        await user_repo.update_user_language(user_id, new_lang)
        return True
    except Exception:
        return False

def is_valid_language_code(lang_code: str) -> bool:
    """Check if language code is valid and supported."""
    return lang_code in get_available_languages()

__all__ = [
    "language_router",
    "get_available_languages", 
    "create_language_keyboard",
    "detect_user_language_from_telegram",
    "get_user_language_preference",
    "create_language_menu_button",
    "apply_language_change",
    "is_valid_language_code"
]
