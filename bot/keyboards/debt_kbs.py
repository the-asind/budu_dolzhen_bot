from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from bot.locales.main import Localization
import json
from typing import Dict, Any


def encode_callback_data(action: str, debt_id: int, **kwargs) -> str:
    """Encode callback data for secure button interactions."""
    data = {
        "action": action,
        "debt_id": debt_id,
        **kwargs
    }
    return json.dumps(data, separators=(',', ':'))


def decode_callback_data(callback_data: str) -> Dict[str, Any]:
    """Decode callback data from button interactions."""
    try:
        return json.loads(callback_data)
    except (json.JSONDecodeError, TypeError):
        return {}


def get_debt_confirmation_kb(debt_id: int, lang: str) -> InlineKeyboardMarkup:
    """Create keyboard for debt confirmation with Agree/Decline buttons."""
    loc = Localization(lang)
    buttons = [
        [
            InlineKeyboardButton(
                text=loc.debt_buttons['agree'], 
                callback_data=encode_callback_data("debt_agree", debt_id)
            ),
            InlineKeyboardButton(
                text=loc.debt_buttons['decline'], 
                callback_data=encode_callback_data("debt_decline", debt_id)
            )
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_payment_confirmation_kb(payment_id: int, debt_id: int, lang: str) -> InlineKeyboardMarkup:
    """Create keyboard for payment confirmation by creditor."""
    loc = Localization(lang)
    buttons = [
        [
            InlineKeyboardButton(
                text=loc.payment_buttons['approve'], 
                callback_data=encode_callback_data("payment_approve", debt_id, payment_id=payment_id)
            ),
            InlineKeyboardButton(
                text=loc.payment_buttons['reject'], 
                callback_data=encode_callback_data("payment_reject", debt_id, payment_id=payment_id)
            )
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_debt_status_kb(debt_id: int, status: str, lang: str) -> InlineKeyboardMarkup:
    """Create keyboard for debt status updates with appropriate actions."""
    loc = Localization(lang)
    buttons = []
    
    if status == "pending":
        buttons.append([
            InlineKeyboardButton(
                text=loc.debt_buttons['cancel'], 
                callback_data=encode_callback_data("debt_cancel", debt_id)
            )
        ])
    elif status == "active":
        buttons.extend([
            [
                InlineKeyboardButton(
                    text=loc.debt_buttons['pay'], 
                    callback_data=encode_callback_data("debt_pay", debt_id)
                )
            ],
            [
                InlineKeyboardButton(
                    text=loc.debt_buttons['details'], 
                    callback_data=encode_callback_data("debt_details", debt_id)
                )
            ]
        ])
    elif status == "rejected":
        buttons.append([
            InlineKeyboardButton(
                text=loc.debt_buttons['recreate'], 
                callback_data=encode_callback_data("debt_recreate", debt_id)
            )
        ])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_payment_status_kb(payment_id: int, debt_id: int, status: str, lang: str) -> InlineKeyboardMarkup:
    """Create keyboard for payment status updates."""
    loc = Localization(lang)
    buttons = []
    
    if status == "pending":
        buttons.append([
            InlineKeyboardButton(
                text=loc.payment_buttons['cancel'], 
                callback_data=encode_callback_data("payment_cancel", debt_id, payment_id=payment_id)
            )
        ])
    elif status == "confirmed":
        buttons.append([
            InlineKeyboardButton(
                text=loc.payment_buttons['receipt'], 
                callback_data=encode_callback_data("payment_receipt", debt_id, payment_id=payment_id)
            )
        ])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_debt_list_kb(debts: list, page: int, lang: str, debt_type: str = "all") -> InlineKeyboardMarkup:
    """Create keyboard for debt list navigation with pagination."""
    loc = Localization(lang)
    buttons = []
    
    # Add debt buttons (max 5 per page)
    start_idx = page * 5
    end_idx = min(start_idx + 5, len(debts))
    
    for debt in debts[start_idx:end_idx]:
        debt_text = f"{debt.amount} {debt.currency} - {debt.description[:20]}..."
        buttons.append([
            InlineKeyboardButton(
                text=debt_text,
                callback_data=encode_callback_data("debt_select", debt.id)
            )
        ])
    
    # Navigation buttons
    nav_buttons = []
    if page > 0:
        nav_buttons.append(
            InlineKeyboardButton(
                text=loc.navigation_buttons['prev'],
                callback_data=encode_callback_data("debt_list_page", 0, page=page-1, debt_type=debt_type)
            )
        )
    
    if end_idx < len(debts):
        nav_buttons.append(
            InlineKeyboardButton(
                text=loc.navigation_buttons['next'],
                callback_data=encode_callback_data("debt_list_page", 0, page=page+1, debt_type=debt_type)
            )
        )
    
    if nav_buttons:
        buttons.append(nav_buttons)
    
    # Filter buttons
    filter_buttons = []
    if debt_type != "active":
        filter_buttons.append(
            InlineKeyboardButton(
                text=loc.debt_filter_buttons['active'],
                callback_data=encode_callback_data("debt_filter", 0, debt_type="active", page=0)
            )
        )
    if debt_type != "pending":
        filter_buttons.append(
            InlineKeyboardButton(
                text=loc.debt_filter_buttons['pending'],
                callback_data=encode_callback_data("debt_filter", 0, debt_type="pending", page=0)
            )
        )
    if debt_type != "all":
        filter_buttons.append(
            InlineKeyboardButton(
                text=loc.debt_filter_buttons['all'],
                callback_data=encode_callback_data("debt_filter", 0, debt_type="all", page=0)
            )
        )
    
    if filter_buttons:
        # Split filter buttons into rows of 2
        for i in range(0, len(filter_buttons), 2):
            buttons.append(filter_buttons[i:i+2])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_debt_actions_kb(debt_id: int, debt_status: str, user_role: str, lang: str) -> InlineKeyboardMarkup:
    """Create keyboard with available actions for a specific debt based on user role and debt status."""
    loc = Localization(lang)
    buttons = []
    
    if user_role == "debtor" and debt_status == "active":
        buttons.extend([
            [
                InlineKeyboardButton(
                    text=loc.debt_actions['pay_full'],
                    callback_data=encode_callback_data("debt_pay_full", debt_id)
                )
            ],
            [
                InlineKeyboardButton(
                    text=loc.debt_actions['pay_partial'],
                    callback_data=encode_callback_data("debt_pay_partial", debt_id)
                )
            ]
        ])
    elif user_role == "creditor" and debt_status == "active":
        buttons.append([
            InlineKeyboardButton(
                text=loc.debt_actions['remind'],
                callback_data=encode_callback_data("debt_remind", debt_id)
            )
        ])
    
    # Common actions
    buttons.extend([
        [
            InlineKeyboardButton(
                text=loc.debt_actions['view_history'],
                callback_data=encode_callback_data("debt_history", debt_id)
            )
        ],
        [
            InlineKeyboardButton(
                text=loc.debt_actions['back_to_list'],
                callback_data=encode_callback_data("debt_back_to_list", debt_id)
            )
        ]
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_processing_kb(lang: str, show_cancel: bool = False) -> InlineKeyboardMarkup:
    """Create keyboard for processing states with optional cancel button."""
    loc = Localization(lang)
    buttons = []
    
    if show_cancel:
        buttons.append([
            InlineKeyboardButton(
                text=loc.processing_buttons['cancel'],
                callback_data=encode_callback_data("process_cancel", 0)
            )
        ])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_debt_summary_kb(user_id: int, lang: str) -> InlineKeyboardMarkup:
    """Create keyboard for debt summary with quick actions."""
    loc = Localization(lang)
    buttons = [
        [
            InlineKeyboardButton(
                text=loc.summary_buttons['view_debts'],
                callback_data=encode_callback_data("view_debts", 0, user_id=user_id)
            ),
            InlineKeyboardButton(
                text=loc.summary_buttons['view_credits'],
                callback_data=encode_callback_data("view_credits", 0, user_id=user_id)
            )
        ],
        [
            InlineKeyboardButton(
                text=loc.summary_buttons['create_debt'],
                callback_data=encode_callback_data("create_debt", 0)
            )
        ],
        [
            InlineKeyboardButton(
                text=loc.summary_buttons['refresh'],
                callback_data=encode_callback_data("refresh_summary", 0, user_id=user_id)
            )
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_mutual_offset_kb(debt_id_1: int, debt_id_2: int, lang: str) -> InlineKeyboardMarkup:
    """Create keyboard for mutual debt offset confirmation."""
    loc = Localization(lang)
    buttons = [
        [
            InlineKeyboardButton(
                text=loc.offset_buttons['confirm'],
                callback_data=encode_callback_data("offset_confirm", debt_id_1, debt_id_2=debt_id_2)
            ),
            InlineKeyboardButton(
                text=loc.offset_buttons['cancel'],
                callback_data=encode_callback_data("offset_cancel", debt_id_1, debt_id_2=debt_id_2)
            )
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_back_to_debt_kb(debt_id: int, lang: str) -> InlineKeyboardMarkup:
    """Create simple back button to return to debt details."""
    loc = Localization(lang)
    buttons = [
        [
            InlineKeyboardButton(
                text=loc.navigation_buttons['back'],
                callback_data=encode_callback_data("back_to_debt", debt_id)
            )
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)
