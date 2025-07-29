import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from aiogram import Bot
from aiogram.types import InlineQuery

from bot.handlers.inline_handlers import handle_inline_query
from bot.core.notification_service import NotificationService
from bot.db.repositories import UserRepository
from bot.db.models import Debt
from bot.core.debt_parser import DebtParser
from bot.core.debt_manager import DebtManager
from tests.conftest import make_mutable_inline_query


@pytest.mark.asyncio
async def test_inline_query_prompts_registration(model_user):
    user = model_user(id=999, is_bot=False, first_name="Test", username="newuser", language_code="en")
    inline_query = make_mutable_inline_query(id="q1", from_user=user, query="@debtor 100")
    inline_query.text = inline_query.query

    bot = AsyncMock(spec=Bot)
    bot.get_me = AsyncMock(return_value=MagicMock(username="testbot"))
    notification_service = AsyncMock(spec=NotificationService)

    with patch.object(UserRepository, "get_by_id", AsyncMock(return_value=None)):
        await handle_inline_query(inline_query, bot, notification_service, lambda k, **kw: k)

    args = inline_query.answer.call_args[0]
    assert args[0][0].id == "register"


@pytest.mark.asyncio
async def test_inline_query_send_all_option(model_user):
    user = model_user(id=1, is_bot=False, first_name="Creditor", username="creditor", language_code="en")
    inline_query = make_mutable_inline_query(id="q2", from_user=user, query="@d1 10\n@d2 20")
    inline_query.text = inline_query.query

    bot = AsyncMock(spec=Bot)
    bot.get_me = AsyncMock(return_value=MagicMock(username="testbot"))
    notification_service = AsyncMock(spec=NotificationService)

    pd1 = MagicMock(amount=1000, combined_comment="pizza")
    pd2 = MagicMock(amount=2000, combined_comment="coffee")
    debt1 = Debt(debt_id=1, creditor_id=1, debtor_id=2, amount=1000, description="pizza", status="pending")
    debt2 = Debt(debt_id=2, creditor_id=1, debtor_id=3, amount=2000, description="coffee", status="pending")

    with patch.object(UserRepository, "get_by_id", AsyncMock(return_value=True)), patch.object(
        DebtParser, "parse", return_value={"d1": pd1, "d2": pd2}
    ), patch.object(DebtManager, "process_message", AsyncMock(return_value=[debt1, debt2])):
        await handle_inline_query(inline_query, bot, notification_service, lambda k, **kw: k)

    results = inline_query.answer.call_args[0][0]
    assert any(r.id == "send_all" for r in results)
