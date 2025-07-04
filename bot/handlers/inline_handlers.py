from aiogram import Router, F
from aiogram.types import InlineQuery, InlineQueryResultArticle, InputTextMessageContent

inline_router = Router(name="inline")

@inline_router.inline_query()
async def handle_inline_query(inline_query: InlineQuery):
    """
    Handles inline queries to create a debt record.
    Example: @bot_username @user 500 for coffee
    """
    # TODO: Parse the inline_query.query using the DebtParser
    # TODO: If parsing is successful, create an InlineQueryResultArticle
    # TODO: If parsing fails, maybe show an article with an error/help message
    
    # Placeholder implementation
    results = [
        InlineQueryResultArticle(
            id="1",
            title="Create a new debt",
            description="Example: @user 500 for coffee",
            input_message_content=InputTextMessageContent(
                message_text="This feature is coming soon!"
            ),
        )
    ]
    
    await inline_query.answer(results, cache_time=1) 