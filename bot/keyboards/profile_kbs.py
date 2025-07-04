from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from bot.locales.main import Localization

def get_settings_menu_kb(lang: str) -> InlineKeyboardMarkup:
    loc = Localization(lang)
    buttons = [
        [InlineKeyboardButton(text=loc.settings_buttons['contact'], callback_data="set_contact")],
        [InlineKeyboardButton(text=loc.settings_buttons['reminders'], callback_data="set_reminders")],
        [InlineKeyboardButton(text=loc.settings_buttons['trusted'], callback_data="manage_trusted")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def back_to_settings_kb(lang: str) -> InlineKeyboardMarkup:
    loc = Localization(lang)
    buttons = [
        [InlineKeyboardButton(text=loc.settings_buttons['back'], callback_data="back_to_settings")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons) 