from aiogram import Router
from aiogram.types import (
    InlineQuery,
    InlineQueryResultArticle,
    InputTextMessageContent,
    InlineQueryResultsButton,
)
from bot.core.debt_parser import DebtParser, DebtParseError
from bot.db.repositories import UserRepository
from bot.locales.main import _

inline_router = Router(name="inline")

@inline_router.inline_query()
async def handle_inline_query(inline_query: InlineQuery, _: callable):
    # Check user registration
    if not await UserRepository.get_by_id(inline_query.from_user.id):
        button = InlineQueryResultsButton(
            text=_("inline_registration_title"),
            start_parameter="register",
        )
        await inline_query.answer(results=[], cache_time=1, is_personal=True, button=button)
        return

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

    author = inline_query.from_user.username or ""
    try:
        parsed = DebtParser.parse(query, author_username=author)
    except DebtParseError as e:
        err = InlineQueryResultArticle(
            id="error",
            title=_("debt_parsing_error"),
            description=_(e.key),
            input_message_content=InputTextMessageContent(
                message_text=f"{_('debt_parsing_error')}\n{_('inline_query_format_help')}"
            ),
        )
        await inline_query.answer([err], cache_time=1)
        return

    # Summary lines
    results = []
    lines: list[str] = []

    for idx, (debtor, pd) in enumerate(parsed.items()):
        amount = f"{pd.amount/100:.0f}" if isinstance(pd.amount, int) else str(pd.amount)
        comment = pd.combined_comment or ""
        line = f"@{debtor} {amount} {comment}".strip()
        lines.append(line)

        results.append(
            InlineQueryResultArticle(
                id=f"single_{idx}",
                title = _("inline_debt_title",
                    debtor=debtor,
                    amount=amount),
                description=comment,
                input_message_content=InputTextMessageContent(
                    message_text = _("inline_debt_message",
                        author=author,
                        debtor=debtor,
                        amount=amount,
                        description=comment)
                ),
            )
        )

    # Add "send them all"
    if len(lines) > 1:
        summary = _("inline_bulk_debt_message").format(
            author=author,
            lines="\n".join(lines),
        )
        results.append(
            InlineQueryResultArticle(
                id="all",
                title=_("inline_send_all_option"),
                input_message_content=InputTextMessageContent(message_text=summary),
            )
        )

    await inline_query.answer(results, cache_time=1, is_personal=True)
