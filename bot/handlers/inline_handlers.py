from aiogram import Router, F
from aiogram.types import InlineQuery, InlineQueryResultArticle, InputTextMessageContent, CallbackQuery, Message

from bot.core.debt_parser import DebtParser
from bot.core.debt_manager import DebtManager
from bot.db.repositories import DebtRepository
from bot.db.models import DebtStatus
from bot.keyboards.debt_kbs import get_debt_confirmation_kb, decode_callback_data
from bot.locales.main import _

inline_router = Router(name="inline")


@inline_router.inline_query()
async def handle_inline_query(inline_query: InlineQuery):
    """
    Handles inline queries to create a debt record.
    Example: @bot_username @user 500 for coffee
    """
    query = inline_query.query.strip()
    if not query:
        help_article = InlineQueryResultArticle(
            id="help",
            title=_("inline_help_message"),
            description=_("inline_query_format_help"),
            input_message_content=InputTextMessageContent(
                message_text=_("inline_help_message")
            ),
        )
        await inline_query.answer([help_article], cache_time=1)
        return

    author_username = inline_query.from_user.username or ""
    try:
        parsed = DebtParser.parse(query, author_username=author_username)
        debts = await DebtManager.process_message(query, author_username=author_username)
    except Exception as e:
        error_article = InlineQueryResultArticle(
            id="error",
            title=_("debt_parsing_error"),
            description=str(e),
            input_message_content=InputTextMessageContent(
                message_text=f"{_('debt_parsing_error')}\n{_('inline_query_format_help')}"
            ),
        )
        await inline_query.answer([error_article], cache_time=1)
        return

    results = []
    lang = inline_query.from_user.language_code or "en"
    parsed_items = list(parsed.items())
    for (debtor_username, pd), debt in zip(parsed_items, debts):
        # Display amount in major units
        try:
            amount_display = f"{pd.amount / 100:.2f}"
        except Exception:
            amount_display = str(pd.amount)
        description = pd.combined_comment or ""
        message_text = (
            f"⏳ @{author_username} says @{debtor_username} owes {amount_display}"
            + (f" for '{description}'" if description else "")
        )
        article = InlineQueryResultArticle(
            id=str(debt.debt_id),
            title=f"Debt: @{debtor_username} - {amount_display}",
            description=description,
            input_message_content=InputTextMessageContent(
                message_text=message_text
            ),
            reply_markup=get_debt_confirmation_kb(debt.debt_id, lang),
        )
        results.append(article)

    await inline_query.answer(results, cache_time=1)


@inline_router.callback_query(F.data)
async def handle_debt_callback(callback_query: CallbackQuery):
    """
    Handles callbacks for debt confirmation buttons: agree or decline.
    """
    data = decode_callback_data(callback_query.data or "")
    action = data.get("action")
    debt_id = data.get("debt_id")
    await callback_query.answer()
    if not action or debt_id is None:
        return

    if action == "debt_agree":
        try:
            debt = await DebtRepository.get(debt_id)
            if debt and debt.debtor_id != callback_query.from_user.id:
                text = _("debt_confirmation_unauthorized")
                message = callback_query.message
                if isinstance(message, Message):
                    await message.edit_text(text)
                return
            debt = await DebtManager.confirm_debt(debt_id, debtor_username=callback_query.from_user.username or "")
            text = _("debt_confirmed_success").format(debt_id=debt.debt_id)
        except Exception as e:
            text = f"❌ {e}"
        message = callback_query.message
        if isinstance(message, Message):
            await message.edit_text(text)

    elif action == "debt_decline":
        try:
            debt = await DebtRepository.update_status(debt_id, "rejected")
            text = _("debt_declined_success").format(debt_id=debt.debt_id)
        except Exception as e:
            text = f"❌ {e}"
        message = callback_query.message
        if isinstance(message, Message):
            await message.edit_text(text)
