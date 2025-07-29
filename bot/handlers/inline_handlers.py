# ruff: noqa
from aiogram import Router, F, Bot
from aiogram.types import (
    InlineQuery,
    InlineQueryResultArticle,
    InputTextMessageContent,
    CallbackQuery,
    Message,
    InlineQueryResultsButton,
)

from bot.core.debt_parser import DebtParser, DebtParseError
from bot.core.debt_manager import DebtManager
from bot.db.repositories import DebtRepository, UserRepository
from bot.keyboards.debt_kbs import get_debt_confirmation_kb, decode_callback_data
from bot.locales.main import _
from bot.core.notification_service import NotificationService

inline_router = Router(name="inline")


@inline_router.inline_query()
async def handle_inline_query(
    inline_query: InlineQuery,
    bot: Bot,
    notification_service: NotificationService,
    _: callable,
):
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
            input_message_content=InputTextMessageContent(message_text=_("inline_help_message")),
        )
        await inline_query.answer([help_article], cache_time=1)
        return

    if not await UserRepository.get_by_id(inline_query.from_user.id):
        button = InlineQueryResultsButton(
            text=_("inline_registration_title"),
            start_parameter="register"
        )
        await inline_query.answer(
            results=[],
            cache_time=1,
            is_personal=True,
            button=button
        )
        return

    author_username = inline_query.from_user.username or ""
    try:
        parsed = DebtParser.parse(query, author_username=author_username)
        debts = await DebtManager.process_message(query, author_username=author_username)
    except DebtParseError as e:
        error_article = InlineQueryResultArticle(
            id="error",
            title=_("debt_parsing_error"),
            description=_(e.key),
            input_message_content=InputTextMessageContent(
                message_text=f"{_('debt_parsing_error')}\n{_('inline_query_format_help')}"
            ),
        )
        await inline_query.answer([error_article], cache_time=1)
        return
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
    lines: list[str] = []
    unregistered: list[str] = []

    creditor = await UserRepository.get_by_username(author_username)

    for (debtor_username, pd), debt in zip(parsed_items, debts):
        try:
            amount_display = f"{pd.amount / 100:.2f}"
        except Exception:
            amount_display = str(pd.amount)

        desc = pd.combined_comment or ""
        lines.append(f"@{debtor_username} {amount_display} {desc}".strip())

        message_text = _("inline_debt_message").format(
            author=author_username,
            debtor=debtor_username,
            amount=amount_display,
            description=desc,
        )

        article = InlineQueryResultArticle(
            id=str(debt.debt_id),
            title=_("inline_debt_title").format(debtor=debtor_username, amount=amount_display),
            description=desc,
            input_message_content=InputTextMessageContent(message_text=message_text),
        )
        results.append(article)

        debtor = await UserRepository.get_by_username(debtor_username)
        if debtor is None:
            unregistered.append(f"@{debtor_username}")
        if debtor and creditor:
            await notification_service.send_debt_confirmation_request(debt, creditor, debtor)

    if len(parsed_items) > 1:
        summary = _("inline_bulk_debt_message").format(author=author_username, lines="\n".join(lines))
        if unregistered:
            summary += "\n" + _("inline_unregistered_notice").format(usernames=", ".join(unregistered))
        results.append(
            InlineQueryResultArticle(
                id="send_all",
                title=_("inline_send_all_option"),
                input_message_content=InputTextMessageContent(message_text=summary),
            )
        )

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
