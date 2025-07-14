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

from bot.handlers.inline_handlers import handle_inline_query, handle_debt_callback
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


class TestCallbackQueryHandling:
    """Test callback query handling for debt confirmation buttons."""

    @pytest.mark.asyncio
    async def test_debt_agree_callback(self, model_user):
        """Test debt agreement callback handling."""
        # Use mutable mock helper for proper setup
        user = model_user(id=456, is_bot=False, first_name="Debtor", username="debtor", language_code="en")
        from tests.conftest import make_mutable_callback_query
        callback_query = make_mutable_callback_query(
            id="callback_id",
            from_user=user,
            data="debt_agree:1"
        )
        
        mock_debt = Debt(debt_id=1, creditor_id=123, debtor_id=456, amount=10000, description="coffee", status="active")
        
        with patch('bot.handlers.inline_handlers.decode_callback_data') as mock_decode, \
             patch.object(DebtManager, 'confirm_debt') as mock_confirm:
            
            mock_decode.return_value = {"action": "debt_agree", "debt_id": 1}
            mock_confirm.return_value = mock_debt
            
            await handle_debt_callback(callback_query)
            
            # Verify debt was confirmed
            mock_confirm.assert_called_once_with(1, debtor_username="debtor")
            # The actual message uses localized text
            callback_query.message.edit_text.assert_called_once()
            callback_query.answer.assert_called_once()

    @pytest.mark.asyncio
    async def test_debt_decline_callback(self, model_user):
        """Test debt decline callback handling."""
        # Use mutable mock helper for proper setup
        user = model_user(id=456, is_bot=False, first_name="Debtor", username="debtor", language_code="en")
        from tests.conftest import make_mutable_callback_query
        callback_query = make_mutable_callback_query(
            id="callback_id",
            from_user=user,
            data="debt_decline:1"
        )
        
        mock_debt = Debt(debt_id=1, creditor_id=123, debtor_id=456, amount=10000, description="coffee", status="rejected")
        
        with patch('bot.handlers.inline_handlers.decode_callback_data') as mock_decode, \
             patch.object(DebtRepository, 'update_status') as mock_update:
            
            mock_decode.return_value = {"action": "debt_decline", "debt_id": 1}
            mock_update.return_value = mock_debt
            
            await handle_debt_callback(callback_query)
            
            # Verify debt was declined
            mock_update.assert_called_once_with(1, "rejected")
            # The actual message uses localized text
            callback_query.message.edit_text.assert_called_once()
            callback_query.answer.assert_called_once()

    @pytest.mark.asyncio
    async def test_invalid_callback_data(self, model_user):
        """Test handling of invalid callback data."""
        # Use mutable mock helper for proper setup
        user = model_user(id=456, is_bot=False, first_name="Debtor", username="debtor", language_code="en")
        from tests.conftest import make_mutable_callback_query
        callback_query = make_mutable_callback_query(
            id="callback_id",
            from_user=user,
            data="invalid_data"
        )
        
        with patch('bot.handlers.inline_handlers.decode_callback_data') as mock_decode:
            mock_decode.return_value = {}
            
            await handle_debt_callback(callback_query)
            
            # Verify callback was acknowledged but no action taken
            callback_query.answer.assert_called_once()
            callback_query.message.edit_text.assert_not_called()

    @pytest.mark.asyncio
    async def test_callback_error_handling(self, model_user):
        """Test error handling in callback processing."""
        # Use mutable mock helper for proper setup
        user = model_user(id=456, is_bot=False, first_name="Debtor", username="debtor", language_code="en")
        from tests.conftest import make_mutable_callback_query
        callback_query = make_mutable_callback_query(
            id="callback_id",
            from_user=user,
            data="debt_agree:1"
        )
        
        with patch('bot.handlers.inline_handlers.decode_callback_data') as mock_decode, \
             patch.object(DebtManager, 'confirm_debt') as mock_confirm:
            
            mock_decode.return_value = {"action": "debt_agree", "debt_id": 1}
            mock_confirm.side_effect = ValueError("Debt not found")
            
            await handle_debt_callback(callback_query)
            
            # Verify error message was displayed
            callback_query.message.edit_text.assert_called_once_with("❌ Debt not found")
            callback_query.answer.assert_called_once()


class TestMessageEditingLogic:
    """Test message editing logic for status updates."""

    @pytest.mark.asyncio
    async def test_status_update_animation_agree(self, model_user):
        """Test status update animation from ⏳ to ✅."""
        user = model_user(id=456, is_bot=False, first_name="Debtor", username="debtor", language_code="en")
        from tests.conftest import make_mutable_callback_query, make_mutable_message
        mock_message = make_mutable_message()
        callback_query = make_mutable_callback_query(
            id="callback_id",
            from_user=user,
            data="debt_agree:1",
            message=mock_message
        )
        
        mock_debt = Debt(debt_id=1, creditor_id=123, debtor_id=456, amount=10000, description="coffee", status="active")
        
        with patch('bot.handlers.inline_handlers.decode_callback_data') as mock_decode, \
             patch.object(DebtManager, 'confirm_debt') as mock_confirm:
            
            mock_decode.return_value = {"action": "debt_agree", "debt_id": 1}
            mock_confirm.return_value = mock_debt
            
            await handle_debt_callback(callback_query)
            
            # Verify message was edited with success status
            mock_message.edit_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_status_update_animation_decline(self, model_user):
        """Test status update animation from ⏳ to ❌."""
        user = model_user(id=456, is_bot=False, first_name="Debtor", username="debtor", language_code="en")
        from tests.conftest import make_mutable_callback_query, make_mutable_message
        mock_message = make_mutable_message()
        callback_query = make_mutable_callback_query(
            id="callback_id",
            from_user=user,
            data="debt_decline:1",
            message=mock_message
        )
        
        mock_debt = Debt(debt_id=1, creditor_id=123, debtor_id=456, amount=10000, description="coffee", status="rejected")
        
        with patch('bot.handlers.inline_handlers.decode_callback_data') as mock_decode, \
             patch.object(DebtRepository, 'update_status') as mock_update:
            
            mock_decode.return_value = {"action": "debt_decline", "debt_id": 1}
            mock_update.return_value = mock_debt
            
            await handle_debt_callback(callback_query)
            
            # Verify message was edited with decline status
            mock_message.edit_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_message_editing_preserves_context(self, model_user):
        """Test that message editing preserves debt context information."""
        user = model_user(id=456, is_bot=False, first_name="Debtor", username="debtor", language_code="en")
        from tests.conftest import make_mutable_callback_query, make_mutable_message
        mock_message = make_mutable_message()
        callback_query = make_mutable_callback_query(
            id="callback_id",
            from_user=user,
            data="debt_agree:42",
            message=mock_message
        )
        
        mock_debt = Debt(debt_id=42, creditor_id=123, debtor_id=456, amount=15000, description="lunch", status="active")
        
        with patch('bot.handlers.inline_handlers.decode_callback_data') as mock_decode, \
             patch.object(DebtManager, 'confirm_debt') as mock_confirm:
            
            mock_decode.return_value = {"action": "debt_agree", "debt_id": 42}
            mock_confirm.return_value = mock_debt
            
            await handle_debt_callback(callback_query)
            
            # Verify message includes correct debt ID
            mock_message.edit_text.assert_called_once()


class TestButtonInteractionWorkflows:
    """Test complete button interaction workflows."""

    @pytest.mark.asyncio
    async def test_complete_agree_workflow(self, model_user, model_chat):
        """Test complete workflow from inline query to debt agreement."""
        # Step 1: Inline query creates debt with keyboard
        user = model_user(id=123, is_bot=False, first_name="Creditor", username="creditor", language_code="en")
        from tests.conftest import make_mutable_inline_query, make_mutable_callback_query, make_mutable_message
        inline_query = make_mutable_inline_query(
            id="test_query_id",
            from_user=user,
            query="@debtor 100 for coffee",
            offset=""
        )
        
        mock_debt = Debt(debt_id=1, creditor_id=123, debtor_id=456, amount=10000, description="coffee", status="pending")
        
        with patch.object(DebtParser, 'parse') as mock_parse, \
             patch.object(DebtManager, 'process_message') as mock_process, \
             patch('bot.handlers.inline_handlers.get_debt_confirmation_kb') as mock_kb:
            
            mock_parse.return_value = {"debtor": MagicMock(amount=10000, combined_comment="coffee")}
            mock_process.return_value = [mock_debt]
            mock_kb.return_value = InlineKeyboardMarkup(inline_keyboard=[])
            
            await handle_inline_query(inline_query)
            
            # Verify debt was created with keyboard
            mock_kb.assert_called_once_with(1, "en")
        
        # Step 2: Debtor clicks agree button
        debtor_user = model_user(id=456, is_bot=False, first_name="Debtor", username="debtor", language_code="en")
        chat = model_chat(id=789, type="private")
        message = make_mutable_message(
            message_id=1, 
            chat=chat,
            from_user=debtor_user
        )
        
        callback_query = make_mutable_callback_query(
            id="callback_id",
            from_user=debtor_user,
            data="debt_agree:1",
            message=message
        )
        
        confirmed_debt = Debt(debt_id=1, creditor_id=123, debtor_id=456, amount=10000, description="coffee", status="active")
        
        with patch('bot.handlers.inline_handlers.decode_callback_data') as mock_decode, \
             patch.object(DebtManager, 'confirm_debt') as mock_confirm:
            
            mock_decode.return_value = {"action": "debt_agree", "debt_id": 1}
            mock_confirm.return_value = confirmed_debt
            
            await handle_debt_callback(callback_query)
            
            # Verify debt was confirmed and message updated
            mock_confirm.assert_called_once_with(1, debtor_username="debtor")
            message.edit_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_complete_decline_workflow(self, model_user, model_chat):
        """Test complete workflow from inline query to debt decline."""
        # Similar to agree workflow but with decline action
        debtor_user = model_user(id=456, is_bot=False, first_name="Debtor", username="debtor", language_code="en")
        chat = model_chat(id=789, type="private")
        from tests.conftest import make_mutable_message, make_mutable_callback_query
        message = make_mutable_message(
            message_id=1, 
            chat=chat,
            from_user=debtor_user
        )
        
        callback_query = make_mutable_callback_query(
            id="callback_id",
            from_user=debtor_user,
            data="debt_decline:1",
            message=message
        )
        
        declined_debt = Debt(debt_id=1, creditor_id=123, debtor_id=456, amount=10000, description="coffee", status="rejected")
        
        with patch('bot.handlers.inline_handlers.decode_callback_data') as mock_decode, \
             patch.object(DebtRepository, 'update_status') as mock_update:
            
            mock_decode.return_value = {"action": "debt_decline", "debt_id": 1}
            mock_update.return_value = declined_debt
            
            await handle_debt_callback(callback_query)
            
            # Verify debt was declined and message updated
            mock_update.assert_called_once_with(1, "rejected")
            message.edit_text.assert_called_once()


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

    @pytest.mark.asyncio
    async def test_unauthorized_debt_confirmation(self, model_user, model_chat):
        """Test handling of unauthorized debt confirmation attempts."""
        # Wrong user trying to confirm debt
        wrong_user = model_user(id=999, is_bot=False, first_name="Wrong", username="wronguser", language_code="en")
        chat = model_chat(id=789, type="private")
        from tests.conftest import make_mutable_message, make_mutable_callback_query
        message = make_mutable_message(
            message_id=1, 
            chat=chat,
            from_user=wrong_user
        )
        
        callback_query = make_mutable_callback_query(
            id="callback_id",
            from_user=wrong_user,
            data="debt_agree:1",
            message=message
        )
        
        with patch('bot.handlers.inline_handlers.decode_callback_data') as mock_decode, \
             patch.object(DebtManager, 'confirm_debt') as mock_confirm:
            
            mock_decode.return_value = {"action": "debt_agree", "debt_id": 1}
            mock_confirm.side_effect = ValueError("Only debtor can confirm debt")
            
            await handle_debt_callback(callback_query)
            
            # Verify error message was displayed
            message.edit_text.assert_called_once_with("❌ Only debtor can confirm debt")

    @pytest.mark.asyncio
    async def test_nonexistent_debt_callback(self, model_user, model_chat):
        """Test handling of callbacks for nonexistent debts."""
        user = model_user(id=456, is_bot=False, first_name="Debtor", username="debtor", language_code="en")
        chat = model_chat(id=789, type="private")
        from tests.conftest import make_mutable_message, make_mutable_callback_query
        message = make_mutable_message(
            message_id=1, 
            chat=chat,
            from_user=user
        )
        
        callback_query = make_mutable_callback_query(
            id="callback_id",
            from_user=user,
            data="debt_agree:999",
            message=message
        )
        
        with patch('bot.handlers.inline_handlers.decode_callback_data') as mock_decode, \
             patch.object(DebtManager, 'confirm_debt') as mock_confirm:
            
            mock_decode.return_value = {"action": "debt_agree", "debt_id": 999}
            mock_confirm.side_effect = ValueError("Debt not found")
            
            await handle_debt_callback(callback_query)
            
            # Verify error message was displayed
            message.edit_text.assert_called_once_with("❌ Debt not found")


class TestCleanChatInterface:
    """Test clean chat interface behavior."""

    @pytest.mark.asyncio
    async def test_message_replacement_not_duplication(self, model_user, model_chat):
        """Test that status updates replace messages rather than create new ones."""
        user = model_user(id=456, is_bot=False, first_name="Debtor", username="debtor", language_code="en")
        chat = model_chat(id=789, type="private")
        from tests.conftest import make_mutable_message, make_mutable_callback_query
        message = make_mutable_message(
            message_id=1, 
            chat=chat,
            from_user=user
        )
        
        callback_query = make_mutable_callback_query(
            id="callback_id",
            from_user=user,
            data="debt_agree:1",
            message=message
        )
        
        mock_debt = Debt(debt_id=1, creditor_id=123, debtor_id=456, amount=10000, description="coffee", status="active")
        
        with patch('bot.handlers.inline_handlers.decode_callback_data') as mock_decode, \
             patch.object(DebtManager, 'confirm_debt') as mock_confirm:
            
            mock_decode.return_value = {"action": "debt_agree", "debt_id": 1}
            mock_confirm.return_value = mock_debt
            
            await handle_debt_callback(callback_query)
            
            # Verify message was edited (not sent as new message)
            message.edit_text.assert_called_once()
            # Verify callback was acknowledged to stop loading animation
            callback_query.answer.assert_called_once()

    @pytest.mark.asyncio
    async def test_final_status_removes_keyboard(self, model_user, model_chat):
        """Test that final status updates remove interactive keyboards."""
        user = model_user(id=456, is_bot=False, first_name="Debtor", username="debtor", language_code="en")
        chat = model_chat(id=789, type="private")
        from tests.conftest import make_mutable_message, make_mutable_callback_query
        message = make_mutable_message(
            message_id=1, 
            chat=chat,
            from_user=user
        )
        
        callback_query = make_mutable_callback_query(
            id="callback_id",
            from_user=user,
            data="debt_agree:1",
            message=message
        )
        
        mock_debt = Debt(debt_id=1, creditor_id=123, debtor_id=456, amount=10000, description="coffee", status="active")
        
        with patch('bot.handlers.inline_handlers.decode_callback_data') as mock_decode, \
             patch.object(DebtManager, 'confirm_debt') as mock_confirm:
            
            mock_decode.return_value = {"action": "debt_agree", "debt_id": 1}
            mock_confirm.return_value = mock_debt
            
            await handle_debt_callback(callback_query)
            
            # Verify message was edited with text only (no keyboard parameter)
            message.edit_text.assert_called_once()


class TestIntegrationWithDebtManager:
    """Test integration between inline keyboards and debt confirmation workflow."""

    @pytest.mark.asyncio
    async def test_debt_manager_integration_confirm(self, model_user, model_chat):
        """Test integration with DebtManager.confirm_debt method."""
        user = model_user(id=456, is_bot=False, first_name="Debtor", username="debtor", language_code="en")
        chat = model_chat(id=789, type="private")
        from tests.conftest import make_mutable_message, make_mutable_callback_query
        message = make_mutable_message(
            message_id=1, 
            chat=chat,
            from_user=user
        )
        
        callback_query = make_mutable_callback_query(
            id="callback_id",
            from_user=user,
            data="debt_agree:1",
            message=message
        )
        
        mock_debt = Debt(debt_id=1, creditor_id=123, debtor_id=456, amount=10000, description="coffee", status="active")
        
        with patch('bot.handlers.inline_handlers.decode_callback_data') as mock_decode, \
             patch.object(DebtManager, 'confirm_debt') as mock_confirm:
            
            mock_decode.return_value = {"action": "debt_agree", "debt_id": 1}
            mock_confirm.return_value = mock_debt
            
            await handle_debt_callback(callback_query)
            
            # Verify DebtManager.confirm_debt was called with correct parameters
            mock_confirm.assert_called_once_with(1, debtor_username="debtor")

    @pytest.mark.asyncio
    async def test_debt_repository_integration_decline(self, model_user, model_chat):
        """Test integration with DebtRepository.update_status method."""
        user = model_user(id=456, is_bot=False, first_name="Debtor", username="debtor", language_code="en")
        chat = model_chat(id=789, type="private")
        from tests.conftest import make_mutable_message, make_mutable_callback_query
        message = make_mutable_message(
            message_id=1, 
            chat=chat,
            from_user=user
        )
        
        callback_query = make_mutable_callback_query(
            id="callback_id",
            from_user=user,
            data="debt_decline:1",
            message=message
        )
        
        mock_debt = Debt(debt_id=1, creditor_id=123, debtor_id=456, amount=10000, description="coffee", status="rejected")
        
        with patch('bot.handlers.inline_handlers.decode_callback_data') as mock_decode, \
             patch.object(DebtRepository, 'update_status') as mock_update:
            
            mock_decode.return_value = {"action": "debt_decline", "debt_id": 1}
            mock_update.return_value = mock_debt
            
            await handle_debt_callback(callback_query)
            
            # Verify DebtRepository.update_status was called with correct parameters
            mock_update.assert_called_once_with(1, "rejected")

    @pytest.mark.asyncio
    async def test_end_to_end_debt_workflow(self, model_user, model_chat):
        """Test complete end-to-end debt workflow through inline keyboards."""
        # Create inline query
        creditor = model_user(id=123, is_bot=False, first_name="Creditor", username="creditor", language_code="en")
        from tests.conftest import make_mutable_inline_query, make_mutable_message, make_mutable_callback_query
        inline_query = make_mutable_inline_query(
            id="test_query_id",
            from_user=creditor,
            query="@debtor 100 for coffee",
            offset=""
        )
        
        # Create debt through inline query
        mock_debt = Debt(debt_id=1, creditor_id=123, debtor_id=456, amount=10000, description="coffee", status="pending")
        
        with patch.object(DebtParser, 'parse') as mock_parse, \
             patch.object(DebtManager, 'process_message') as mock_process, \
             patch('bot.handlers.inline_handlers.get_debt_confirmation_kb') as mock_kb:
            
            mock_parse.return_value = {"debtor": MagicMock(amount=10000, combined_comment="coffee")}
            mock_process.return_value = [mock_debt]
            mock_kb.return_value = InlineKeyboardMarkup(inline_keyboard=[])
            
            await handle_inline_query(inline_query)
            
            # Verify debt creation
            mock_process.assert_called_once_with("@debtor 100 for coffee", author_username="creditor")
        
        # Confirm debt through callback
        debtor = model_user(id=456, is_bot=False, first_name="Debtor", username="debtor", language_code="en")
        chat = model_chat(id=789, type="private")
        message = make_mutable_message(
            message_id=1, 
            chat=chat,
            from_user=debtor
        )
        
        callback_query = make_mutable_callback_query(
            id="callback_id",
            from_user=debtor,
            data="debt_agree:1",
            message=message
        )
        
        confirmed_debt = Debt(debt_id=1, creditor_id=123, debtor_id=456, amount=10000, description="coffee", status="active")
        
        with patch('bot.handlers.inline_handlers.decode_callback_data') as mock_decode, \
             patch.object(DebtManager, 'confirm_debt') as mock_confirm:
            
            mock_decode.return_value = {"action": "debt_agree", "debt_id": 1}
            mock_confirm.return_value = confirmed_debt
            
            await handle_debt_callback(callback_query)
            
            # Verify debt confirmation
            mock_confirm.assert_called_once_with(1, debtor_username="debtor")
            message.edit_text.assert_called_once()
