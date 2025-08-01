"""Comprehensive tests for inline keyboard functionality."""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from aiogram.types import (
    InlineQuery,
    InlineQueryResultArticle,
    CallbackQuery,
    Message,
    User,
    Chat,
    InlineKeyboardMarkup,
)

from bot.handlers.inline_handlers import handle_inline_query
from bot.core.debt_manager import DebtManager
from bot.core.debt_parser import DebtParser
from bot.db.repositories import DebtRepository
from bot.db.models import Debt


class TestInlineKeyboardGeneration:
    """Test inline keyboard generation for different debt scenarios."""

    @pytest.fixture
    def mock_inline_query(self, model_user):
        """Create a mock inline query using mutable mock helper."""
        user = model_user(id=123, is_bot=False, first_name="Test", username="testuser", language_code="en")
        from tests.conftest import make_mutable_inline_query
        query = make_mutable_inline_query(
            id="test_query_id",
            from_user=user,
            query="@debtor 100 for coffee",
            offset=""
        )
        return query

    @pytest.fixture
    def mock_debt(self):
        """Create a mock debt object."""
        return Debt(
            debt_id=1,
            creditor_id=123,
            debtor_id=456,
            amount=10000,  # 100.00 in minor units
            description="coffee",
            status="pending"
        )

    @pytest.mark.asyncio
    async def test_inline_query_generates_keyboard(self, mock_inline_query, mock_debt):
        """Test that inline queries generate proper keyboards."""
        with patch.object(DebtParser, 'parse') as mock_parse, \
             patch.object(DebtManager, 'process_message') as mock_process, \
             patch('bot.handlers.inline_handlers.get_debt_confirmation_kb') as mock_kb:
            
            # Setup mocks with proper async handling
            mock_parse.return_value = {"debtor": MagicMock(amount=10000, combined_comment="coffee")}
            mock_process.return_value = [mock_debt]
            mock_kb.return_value = InlineKeyboardMarkup(inline_keyboard=[])
            
            await handle_inline_query(mock_inline_query)
            
            # Verify keyboard was generated
            mock_kb.assert_called_once_with(1, "en")
            mock_inline_query.answer.assert_called_once()

    @pytest.mark.asyncio
    async def test_inline_query_different_languages(self, model_user, mock_debt):
        """Test keyboard generation for different languages."""
        user = model_user(id=123, is_bot=False, first_name="Test", username="testuser", language_code="ru")
        from tests.conftest import make_mutable_inline_query
        inline_query = make_mutable_inline_query(
            id="test_query_id",
            from_user=user,
            query="@debtor 100 for coffee",
            offset=""
        )
        
        with patch.object(DebtParser, 'parse') as mock_parse, \
             patch.object(DebtManager, 'process_message') as mock_process, \
             patch('bot.handlers.inline_handlers.get_debt_confirmation_kb') as mock_kb:
            
            mock_parse.return_value = {"debtor": MagicMock(amount=10000, combined_comment="coffee")}
            mock_process.return_value = [mock_debt]
            mock_kb.return_value = InlineKeyboardMarkup(inline_keyboard=[])
            
            await handle_inline_query(inline_query)
            
            # Verify keyboard was generated with Russian language
            mock_kb.assert_called_once_with(1, "ru")

    @pytest.mark.asyncio
    async def test_empty_query_shows_help(self, model_user):
        """Test that empty queries show help with proper keyboard."""
        user = model_user(id=123, is_bot=False, first_name="Test", username="testuser", language_code="en")
        from tests.conftest import make_mutable_inline_query
        inline_query = make_mutable_inline_query(
            id="test_query_id",
            from_user=user,
            query="",
            offset=""
        )
        
        await handle_inline_query(inline_query)
        
        # Verify help article was returned
        args = inline_query.answer.call_args[0]
        assert len(args[0]) == 1
        assert args[0][0].id == "help"
        assert "inline_query_format_help" in args[0][0].description

    @pytest.mark.asyncio
    async def test_multiple_debts_generate_multiple_keyboards(self, model_user):
        """Test that multiple debts generate multiple keyboard results."""
        user = model_user(id=123, is_bot=False, first_name="Test", username="testuser", language_code="en")
        from tests.conftest import make_mutable_inline_query
        inline_query = make_mutable_inline_query(
            id="test_query_id",
            from_user=user,
            query="@debtor 100 for coffee",
            offset=""
        )
        debt1 = Debt(debt_id=1, creditor_id=123, debtor_id=456, amount=10000, description="coffee", status="pending")
        debt2 = Debt(debt_id=2, creditor_id=123, debtor_id=789, amount=20000, description="lunch", status="pending")
        
        with patch.object(DebtParser, 'parse') as mock_parse, \
             patch.object(DebtManager, 'process_message') as mock_process, \
             patch('bot.handlers.inline_handlers.get_debt_confirmation_kb') as mock_kb:
            
            mock_parse.return_value = {
                "debtor1": MagicMock(amount=10000, combined_comment="coffee"),
                "debtor2": MagicMock(amount=20000, combined_comment="lunch")
            }
            mock_process.return_value = [debt1, debt2]
            mock_kb.return_value = InlineKeyboardMarkup(inline_keyboard=[])
            
            await handle_inline_query(inline_query)
            
            # Verify keyboards were generated for both debts
            assert mock_kb.call_count == 2
            mock_kb.assert_any_call(1, "en")
            mock_kb.assert_any_call(2, "en")

class TestErrorScenarios:
    """Test error scenarios in inline keyboard interactions."""

    @pytest.mark.asyncio
    async def test_parsing_error_in_inline_query(self, model_user):
        """Test handling of parsing errors in inline queries."""
        user = model_user(id=123, is_bot=False, first_name="Test", username="testuser", language_code="en")
        from tests.conftest import make_mutable_inline_query
        inline_query = make_mutable_inline_query(
            id="test_query_id",
            from_user=user,
            query="invalid query format",
            offset=""
        )
        
        with patch.object(DebtParser, 'parse') as mock_parse:
            mock_parse.side_effect = ValueError("Invalid format")
            
            await handle_inline_query(inline_query)
            
            # Verify error article was returned
            args = inline_query.answer.call_args[0]
            assert len(args[0]) == 1
            assert args[0][0].id == "error"
            assert "debt_parsing_error" in args[0][0].title or "Please check your format" in args[0][0].title

    @pytest.mark.asyncio
    async def test_debt_manager_error_in_inline_query(self, model_user):
        """Test handling of debt manager errors in inline queries."""
        user = model_user(id=123, is_bot=False, first_name="Test", username="testuser", language_code="en")
        from tests.conftest import make_mutable_inline_query
        inline_query = make_mutable_inline_query(
            id="test_query_id",
            from_user=user,
            query="@debtor 100 for coffee",
            offset=""
        )
        
        with patch.object(DebtParser, 'parse') as mock_parse, \
             patch.object(DebtManager, 'process_message') as mock_process:
            
            mock_parse.return_value = {"debtor": MagicMock(amount=10000, combined_comment="coffee")}
            mock_process.side_effect = Exception("Database error")
            
            await handle_inline_query(inline_query)
            
            # Verify error article was returned
            args = inline_query.answer.call_args[0]
            assert len(args[0]) == 1
            assert args[0][0].id == "error"
            assert "Database error" in args[0][0].description
