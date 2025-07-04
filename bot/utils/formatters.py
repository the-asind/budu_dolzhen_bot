from decimal import Decimal

from aiogram.utils.markdown import hlink, hbold, hcode

from bot.db.models import User

__all__ = ["format_amount", "format_user_link", "format_debt_status_emoji", "hlink", "hbold", "hcode"]

def format_amount(amount_in_cents: int) -> str:
    """Formats an amount from cents to a human-readable string."""
    amount = Decimal(amount_in_cents) / 100
    # Format to 2 decimal places, trimming trailing zeros if it's a whole number
    return f"{amount:g}"

def format_user_link(user: User) -> str:
    """Formats a user's name as a Telegram link."""
    full_name = user.first_name
    if user.last_name:
        full_name += f" {user.last_name}"
    
    return hlink(full_name, f"tg://user?id={user.user_id}")

def format_debt_status_emoji(status: str) -> str:
    """Returns an emoji corresponding to the debt status."""
    emojis = {
        "pending": "⏳",
        "active": "✅",
        "paid": "✅",
        "rejected": "❌",
    }
    return emojis.get(status, "❓") 