from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from bot.locales.main import Localization

def get_settings_menu_kb(lang: str) -> InlineKeyboardMarkup:
    loc = Localization(lang)
    sb = loc.settings_buttons or {}
    buttons = [
        [InlineKeyboardButton(text=sb.get('contact', 'Contact'), callback_data="set_contact")],
        [InlineKeyboardButton(text=sb.get('reminders', 'Reminders'), callback_data="set_reminders")],
        [InlineKeyboardButton(text=sb.get('trusted', 'Trusted'), callback_data="manage_trusted")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def back_to_settings_kb(lang: str) -> InlineKeyboardMarkup:
    loc = Localization(lang)
    sb = loc.settings_buttons or {}
    buttons = [
        [InlineKeyboardButton(text=sb.get('back', 'Back'), callback_data="back_to_settings")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons) 
