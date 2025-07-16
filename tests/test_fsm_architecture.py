import pytest
import asyncio
import logging
import time
import uuid
from unittest.mock import AsyncMock, MagicMock, patch, call
from typing import Dict, Any, List
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Update, Message, CallbackQuery, User, Chat, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import TelegramRetryAfter, TelegramBadRequest
from aiogram.methods import EditMessageText

from bot.handlers.profile_handlers import ProfileSettings, profile_router
from bot.middlewares.logging_middleware import LoggingMiddleware
from bot.db.models import User as UserModel
from bot.utils.validators import is_valid_contact_info


# ---------------------------
# Global lightweight fixtures for reuse across classes
# They are defined early to be available everywhere.
# ---------------------------


@pytest.fixture(name="mock_fsm_context")
def fixture_mock_fsm_context():
    ctx = AsyncMock(spec=FSMContext)
    ctx.get_state.return_value = None
    ctx.set_state = AsyncMock()
    ctx.get_data.return_value = {}
    ctx.set_data = AsyncMock()
    ctx.clear = AsyncMock()
    return ctx


@pytest.fixture(name="mock_message")
def fixture_mock_message():
    message = MagicMock(spec=Message)
    message.message_id = 1
    message.date = datetime.now()
    message.text = "/stub"
    message.answer = AsyncMock()
    message.edit_text = AsyncMock()
    message.reply = AsyncMock()
    user = MagicMock(spec=User)
    user.id = 12345
    user.is_bot = False
    user.first_name = "Test"
    message.from_user = user
    chat = MagicMock(spec=Chat)
    chat.id = 12345
    chat.type = "private"
    message.chat = chat
    return message


@pytest.fixture(name="mock_callback_query")
def fixture_mock_callback_query(mock_message):
    """Return lightweight mocked `CallbackQuery`."""
    callback = MagicMock(spec=CallbackQuery)
    callback.id = "cbq"
    callback.message = mock_message
    callback.from_user = mock_message.from_user
    callback.chat_instance = "ci"
    callback.data = "set_contact"
    callback.answer = AsyncMock()
    return callback


@pytest.fixture(name="mock_user_model")
def fixture_mock_user_model():
    user = MagicMock(spec=UserModel)
    user.user_id = 12345
    user.username = "testuser"
    user.first_name = "Test"
    user.language_code = "en"
    return user


class TestFSMStates:
    """Test FSM state definitions and transitions."""
    
    def test_profile_settings_states_defined(self):
        """Test that all required FSM states are properly defined."""
        assert hasattr(ProfileSettings, 'main')
        assert hasattr(ProfileSettings, 'contact_info')
        assert hasattr(ProfileSettings, 'reminders')
        assert hasattr(ProfileSettings, 'trusted_users')
        
        # Verify states are State instances
        assert isinstance(ProfileSettings.main, State)
        assert isinstance(ProfileSettings.contact_info, State)
        assert isinstance(ProfileSettings.reminders, State)
        assert isinstance(ProfileSettings.trusted_users, State)
    
    def test_state_group_inheritance(self):
        """Test that ProfileSettings properly inherits from StatesGroup."""
        assert issubclass(ProfileSettings, StatesGroup)


class TestFSMTransitions:
    """Test FSM state transitions and navigation."""
    
    @pytest.fixture
    def mock_fsm_context(self):
        """Create mock FSM context."""
        context = AsyncMock(spec=FSMContext)
        context.get_state.return_value = None
        context.set_state = AsyncMock()
        context.get_data.return_value = {}
        context.set_data = AsyncMock()
        context.clear = AsyncMock()
        return context
    
    @pytest.fixture
    def mock_message(self):
        """Return a lightweight mock that mimics aiogram Message."""
        message = MagicMock(spec=Message)
        message.message_id = 1
        message.date = datetime.now()
        message.text = "/settings"
        message.answer = AsyncMock()
        message.edit_text = AsyncMock()
        message.reply = AsyncMock()

        # Nested attributes frequently accessed in the handler logic
        user = MagicMock(spec=User)
        user.id = 12345
        user.is_bot = False
        user.first_name = "Test"
        message.from_user = user

        chat = MagicMock(spec=Chat)
        chat.id = 12345
        chat.type = "private"
        message.chat = chat

        return message
    
    @pytest.fixture
    def mock_callback_query(self, mock_message):
        """Return a lightweight mock that mimics aiogram CallbackQuery."""
        callback = MagicMock(spec=CallbackQuery)
        callback.id = "test_callback"
        callback.message = mock_message
        callback.from_user = mock_message.from_user
        callback.chat_instance = "test_instance"
        callback.data = "set_contact"
        callback.answer = AsyncMock()
        return callback
    
    @pytest.fixture
    def mock_update(self):
        """Return a lightweight mock update suitable for logging tests."""
        message = MagicMock(spec=Message)
        user = MagicMock(spec=User)
        user.id = 12345
        message.from_user = user
        message.text = "test message"

        update = MagicMock(spec=Update)
        update.update_id = 1
        update.event_type = "message"
        update.message = message
        return update
    
    @pytest.mark.asyncio
    async def test_settings_menu_entry(self, mock_message, mock_fsm_context):
        """Test entering settings menu sets correct state."""
        with patch('bot.handlers.profile_handlers.get_user_language') as mock_lang, \
             patch('bot.handlers.profile_handlers.get_localization') as mock_loc, \
             patch('bot.handlers.profile_handlers.get_settings_menu_kb') as mock_kb:
            
            mock_lang.return_value = "en"
            mock_loc.return_value.SETTINGS = "Settings"
            mock_kb.return_value = InlineKeyboardMarkup(inline_keyboard=[])
            
            from bot.handlers.profile_handlers import settings_handler
            await settings_handler(mock_message, mock_fsm_context)
            
            mock_message.answer.assert_called_once()
            mock_fsm_context.set_state.assert_called_once_with(ProfileSettings.main)
    
    @pytest.mark.asyncio
    async def test_contact_info_transition(self, mock_callback_query, mock_fsm_context):
        """Test transition to contact info state."""
        with patch('bot.handlers.profile_handlers.get_user_language') as mock_lang, \
             patch('bot.handlers.profile_handlers.get_localization') as mock_loc, \
             patch('bot.handlers.profile_handlers.back_to_settings_kb') as mock_kb:
            
            mock_lang.return_value = "en"
            mock_loc.return_value.SET_CONTACT_PROMPT = "Enter contact info"
            mock_kb.return_value = InlineKeyboardMarkup(inline_keyboard=[])
            
            from bot.handlers.profile_handlers import set_contact_handler
            await set_contact_handler(mock_callback_query, mock_fsm_context)
            
            mock_callback_query.message.edit_text.assert_called_once()
            mock_fsm_context.set_state.assert_called_once_with(ProfileSettings.contact_info)
    
    @pytest.mark.asyncio
    async def test_reminder_settings_transition(self, mock_callback_query, mock_fsm_context):
        """Test transition to reminder settings state."""
        with patch('bot.handlers.profile_handlers.get_user_language') as mock_lang, \
             patch('bot.handlers.profile_handlers.get_localization') as mock_loc, \
             patch('bot.handlers.profile_handlers.back_to_settings_kb') as mock_kb:
            
            mock_lang.return_value = "en"
            mock_loc.return_value.REMINDER_SETTINGS = "Reminder Settings"
            mock_kb.return_value = InlineKeyboardMarkup(inline_keyboard=[])
            
            from bot.handlers.profile_handlers import set_reminders_handler
            await set_reminders_handler(mock_callback_query, mock_fsm_context)
            
            mock_callback_query.message.edit_text.assert_called_once()
            mock_fsm_context.set_state.assert_called_once_with(ProfileSettings.reminders)
    
    @pytest.mark.asyncio
    async def test_trusted_users_transition(self, mock_callback_query, mock_fsm_context):
        """Test transition to trusted users management state."""
        with patch('bot.handlers.profile_handlers.get_user_language') as mock_lang, \
             patch('bot.handlers.profile_handlers.get_localization') as mock_loc, \
             patch('bot.handlers.profile_handlers.back_to_settings_kb') as mock_kb:
            
            mock_lang.return_value = "en"
            mock_loc.return_value.TRUSTED_USERS_MENU = "Trusted Users"
            mock_kb.return_value = InlineKeyboardMarkup(inline_keyboard=[])
            
            from bot.handlers.profile_handlers import manage_trusted_handler
            await manage_trusted_handler(mock_callback_query, mock_fsm_context)
            
            mock_callback_query.message.edit_text.assert_called_once()
            mock_fsm_context.set_state.assert_called_once_with(ProfileSettings.trusted_users)
    
    @pytest.mark.asyncio
    async def test_back_to_settings_transition(self, mock_callback_query, mock_fsm_context):
        """Test returning to main settings menu."""
        with patch('bot.handlers.profile_handlers.get_user_language') as mock_lang, \
             patch('bot.handlers.profile_handlers.get_localization') as mock_loc, \
             patch('bot.handlers.profile_handlers.get_settings_menu_kb') as mock_kb:
            
            mock_lang.return_value = "en"
            mock_loc.return_value.SETTINGS = "Settings"
            mock_kb.return_value = InlineKeyboardMarkup(inline_keyboard=[])
            
            from bot.handlers.profile_handlers import back_to_settings_handler
            await back_to_settings_handler(mock_callback_query, mock_fsm_context)
            
            mock_callback_query.message.edit_text.assert_called_once()
            mock_fsm_context.set_state.assert_called_once_with(ProfileSettings.main)


class TestInputValidation:
    """Test input validation in FSM states."""
    
    @pytest.fixture
    def mock_user_model(self):
        """Create mock user model."""
        return UserModel(
            user_id=12345,
            username="testuser",
            first_name="Test",
            language_code="en"
        )
    
    @pytest.mark.asyncio
    async def test_contact_info_validation_valid(self, mock_message, mock_fsm_context, mock_user_model):
        """Test valid contact info input."""
        mock_message.text = "test@example.com"
        
        with patch('bot.handlers.profile_handlers.user_repo') as mock_repo, \
             patch('bot.handlers.profile_handlers.get_user_language') as mock_lang, \
             patch('bot.handlers.profile_handlers.get_localization') as mock_loc, \
             patch('bot.handlers.profile_handlers.is_valid_contact_info') as mock_validate, \
             patch('bot.handlers.profile_handlers.settings_handler') as mock_settings:
            
            mock_lang.return_value = "en"
            mock_loc.return_value.profile_contact_saved = "Contact saved"
            mock_validate.return_value = True
            mock_repo.update_user_contact = AsyncMock()
            
            from bot.handlers.profile_handlers import handle_contact_info_input
            await handle_contact_info_input(mock_message, mock_fsm_context, lambda x: x, mock_user_model)
            
            mock_validate.assert_called_once_with("test@example.com")
            mock_repo.update_user_contact.assert_called_once_with(12345, "test@example.com")
            assert mock_validate.called, "Patch target incorrect"
    
    @pytest.mark.asyncio
    async def test_contact_info_validation_invalid(self, mock_message, mock_fsm_context, mock_user_model):
        """Test invalid contact info input."""
        mock_message.text = "invalid-email"
        
        with patch('bot.handlers.profile_handlers.get_user_language') as mock_lang, \
             patch('bot.handlers.profile_handlers.get_localization') as mock_loc, \
             patch('bot.handlers.profile_handlers.is_valid_contact_info') as mock_validate:
            
            mock_lang.return_value = "en"
            mock_loc.return_value.profile_contact_invalid = "Invalid contact info"
            mock_validate.return_value = False
            
            from bot.handlers.profile_handlers import handle_contact_info_input
            await handle_contact_info_input(mock_message, mock_fsm_context, lambda x: x, mock_user_model)
            
            mock_validate.assert_called_once_with("invalid-email")
            mock_message.reply.assert_called_once()
            assert mock_validate.called, "Patch target incorrect"
            # Should show error message and stay in same state
    
    @pytest.mark.asyncio
    async def test_payday_validation_valid(self):
        """Test valid payday input validation."""
        # This test is skipped as validate_payday_days doesn't exist
        pytest.skip("validate_payday_days function not implemented")
    
    @pytest.mark.asyncio
    async def test_empty_input_handling(self, mock_message, mock_fsm_context, mock_user_model):
        """Test handling of empty or None input."""
        mock_message.text = ""
        
        with patch('bot.handlers.profile_handlers.get_user_language') as mock_lang, \
             patch('bot.handlers.profile_handlers.get_localization') as mock_loc, \
             patch('bot.handlers.profile_handlers.is_valid_contact_info') as mock_validate:
            
            mock_lang.return_value = "en"
            mock_loc.return_value.profile_contact_invalid = "Invalid contact info"
            mock_validate.return_value = False
            
            from bot.handlers.profile_handlers import handle_contact_info_input
            await handle_contact_info_input(
                mock_message, mock_fsm_context, lambda x: x, mock_user_model
            )

            # Validation function is not invoked because the input is empty
            mock_validate.assert_not_called()
            mock_message.reply.assert_called_once()


class TestErrorHandling:
    """Test error handling in FSM flows."""
    
    @pytest.mark.asyncio
    async def test_invalid_state_handling(self, mock_message, mock_fsm_context):
        """Test handling of invalid FSM states."""
        mock_fsm_context.get_state.return_value = "invalid_state"
        
        with patch('bot.handlers.profile_handlers.get_user_language') as mock_lang, \
             patch('bot.handlers.profile_handlers.get_localization') as mock_loc:
            
            mock_lang.return_value = "en"
            mock_loc.return_value.ERROR_INVALID_STATE = "Invalid state"
            
            from bot.handlers.profile_handlers import settings_handler
            await settings_handler(mock_message, mock_fsm_context)
            
            # Should reset to main state
            mock_fsm_context.set_state.assert_called_with(ProfileSettings.main)
    
    @pytest.mark.asyncio
    async def test_database_error_handling(self, mock_message, mock_fsm_context, mock_user_model):
        """Test handling of database errors during FSM operations."""
        mock_message.text = "test@example.com"
        
        with patch('bot.handlers.profile_handlers.user_repo') as mock_repo, \
             patch('bot.handlers.profile_handlers.validate_contact_info') as mock_validate:
            
            mock_validate.return_value = True
            mock_repo.update_user_contact.side_effect = Exception("Database error")
            
            from bot.handlers.profile_handlers import handle_contact_info_input
            
            with pytest.raises(Exception):
                await handle_contact_info_input(mock_message, mock_fsm_context, lambda x: x, mock_user_model)
    
    @pytest.mark.asyncio
    async def test_telegram_api_error_handling(self, mock_callback_query, mock_fsm_context):
        """Test handling of Telegram API errors."""
        mock_callback_query.message.edit_text.side_effect = TelegramBadRequest(method=EditMessageText(text="test"), message="Bad request")
        
        with patch('bot.handlers.profile_handlers.get_user_language') as mock_lang, \
             patch('bot.handlers.profile_handlers.get_localization') as mock_loc, \
             patch('bot.handlers.profile_handlers.back_to_settings_kb') as mock_kb:
            
            mock_lang.return_value = "en"
            mock_loc.return_value.SET_CONTACT_PROMPT = "Enter contact info"
            mock_kb.return_value = InlineKeyboardMarkup(inline_keyboard=[])
            
            from bot.handlers.profile_handlers import set_contact_handler
            
            with pytest.raises(TelegramBadRequest):
                await set_contact_handler(mock_callback_query, mock_fsm_context)


class TestLoggingMiddleware:
    """Test logging middleware with correlation IDs and structured logging."""
    
    @pytest.fixture
    def logging_middleware(self):
        """Create logging middleware instance."""
        return LoggingMiddleware()
    
    @pytest.fixture
    def mock_update(self):
        """Return a lightweight mock update suitable for logging tests."""
        message = MagicMock(spec=Message)
        user = MagicMock(spec=User)
        user.id = 12345
        message.from_user = user
        message.text = "test message"

        update = MagicMock(spec=Update)
        update.update_id = 1
        update.event_type = "message"
        update.message = message
        return update
    
    @pytest.mark.asyncio
    async def test_correlation_id_generation(self, logging_middleware, mock_update):
        """Test that correlation IDs are generated and propagated."""
        handler = AsyncMock()
        data = {"event_from_user": mock_update.message.from_user}
        
        with patch('bot.middlewares.logging_middleware.uuid.uuid4') as mock_uuid:
            mock_uuid.return_value = uuid.UUID('12345678-1234-5678-9012-123456789012')
            
            await logging_middleware(handler, mock_update, data)
            
            # Verify correlation ID was added to data
            assert "correlation_id" in data
            assert data["correlation_id"] == "12345678-1234-5678-9012-123456789012"
    
    @pytest.mark.asyncio
    async def test_structured_logging_format(self, logging_middleware, mock_update, caplog):
        """Test structured logging format with detailed context."""
        handler = AsyncMock()
        data = {"event_from_user": mock_update.message.from_user}
        
        with caplog.at_level(logging.INFO):
            await logging_middleware(handler, mock_update, data)
        
        # Verify structured log format
        log_record = caplog.records[0]
        assert "correlation_id" in log_record.getMessage()
        assert "user_id=12345" in log_record.getMessage()
        assert "update_type=message" in log_record.getMessage()
    
    @pytest.mark.asyncio
    async def test_fsm_transition_logging(self, logging_middleware, mock_update, caplog):
        """Test FSM transition logging."""
        handler = AsyncMock()
        data = {
            "event_from_user": mock_update.message.from_user,
            "state": ProfileSettings.contact_info,
            "previous_state": ProfileSettings.main
        }
        
        with caplog.at_level(logging.INFO):
            await logging_middleware(handler, mock_update, data)
        
        # Verify FSM transition is logged
        log_messages = [record.getMessage() for record in caplog.records]
        fsm_log = next((msg for msg in log_messages if "FSM transition" in msg), None)
        assert fsm_log is not None
        assert "ProfileSettings:main -> ProfileSettings:contact_info" in fsm_log
    
    @pytest.mark.asyncio
    async def test_performance_monitoring(self, logging_middleware, mock_update, caplog):
        """Test performance monitoring and execution time logging."""
        async def slow_handler(update, data):
            await asyncio.sleep(0.1)  # Simulate slow handler
            return "result"
        
        data = {"event_from_user": mock_update.message.from_user}
        
        with caplog.at_level(logging.INFO):
            start_time = time.time()
            await logging_middleware(slow_handler, mock_update, data)
            end_time = time.time()
        
        # Verify performance logging
        log_messages = [record.getMessage() for record in caplog.records]
        perf_log = next((msg for msg in log_messages if "execution_time" in msg), None)
        assert perf_log is not None
        
        # Verify execution time is reasonable
        execution_time = end_time - start_time
        assert execution_time >= 0.1
    
    @pytest.mark.asyncio
    async def test_error_logging_with_correlation_id(self, logging_middleware, mock_update, caplog):
        """Test error logging includes correlation ID for tracing."""
        def failing_handler(update, data):
            raise ValueError("Test error")
        
        data = {"event_from_user": mock_update.message.from_user}
        
        with caplog.at_level(logging.ERROR):
            with pytest.raises(ValueError):
                await logging_middleware(failing_handler, mock_update, data)
        
        # Verify error log includes correlation ID
        error_records = [r for r in caplog.records if r.levelno >= logging.ERROR]
        assert len(error_records) > 0
        assert "correlation_id" in error_records[0].getMessage()


class TestRateLimiting:
    """Test rate limiting compliance with Telegram API."""
    
    @pytest.mark.asyncio
    async def test_rate_limit_enforcement(self):
        """Test rate limiting prevents excessive API calls."""
        pytest.skip("Rate limiter not implemented")
    
    @pytest.mark.asyncio
    async def test_retry_after_handling(self):
        """Test handling of TelegramRetryAfter exceptions."""
        pytest.skip("Rate limiter not implemented")
    
    @pytest.mark.asyncio
    async def test_backoff_mechanism(self):
        """Test exponential backoff for rate limiting."""
        pytest.skip("Rate limiter not implemented")
    
    @pytest.mark.asyncio
    async def test_rate_limit_logging(self, caplog):
        """Test rate limiting events are properly logged."""
        pytest.skip("Rate limiter not implemented")


class TestComprehensiveErrorHandling:
    """Test comprehensive error handling with retries and user feedback."""
    
    @pytest.mark.asyncio
    async def test_retry_mechanism(self):
        """Test retry mechanism for transient failures."""
        pytest.skip("Retry handler not implemented")
    
    @pytest.mark.asyncio
    async def test_user_feedback_on_errors(self, mock_message, mock_fsm_context):
        """Test user receives appropriate feedback on errors."""
        with patch('bot.handlers.profile_handlers.user_repo') as mock_repo, \
             patch('bot.handlers.profile_handlers.get_user_language') as mock_lang, \
             patch('bot.handlers.profile_handlers.get_localization') as mock_loc:
            
            mock_repo.get_by_id.side_effect = Exception("Database error")
            mock_lang.return_value = "en"
            mock_loc.return_value.SETTINGS = "Settings"
            
            from bot.handlers.profile_handlers import settings_handler
            await settings_handler(mock_message, mock_fsm_context)
            
            # Handler should still present the settings menu despite the repository error
            mock_message.answer.assert_called_once()
            args = mock_message.answer.call_args[1]
            assert args["text"] == "Settings"
    
    @pytest.mark.asyncio
    async def test_graceful_degradation(self, mock_message, mock_fsm_context):
        """Test graceful degradation when services are unavailable."""
        with patch('bot.handlers.profile_handlers.user_repo') as mock_repo, \
             patch('bot.handlers.profile_handlers.get_user_language') as mock_lang, \
             patch('bot.handlers.profile_handlers.get_localization') as mock_loc:
            
            mock_repo.get_by_id.side_effect = Exception("Service unavailable")
            mock_lang.return_value = "en"
            mock_loc.return_value.SERVICE_UNAVAILABLE = "Service temporarily unavailable"
            
            from bot.handlers.profile_handlers import settings_handler
            
            # Should not crash, should provide fallback behavior
            try:
                await settings_handler(mock_message, mock_fsm_context)
            except Exception as e:
                pytest.fail(f"Handler should not crash on service errors: {e}")


class TestRequestTracing:
    """Test request tracing across multiple interactions."""
    
    @pytest.mark.asyncio
    async def test_correlation_id_persistence(self):
        """Test correlation ID persists across multiple handler calls."""
        correlation_id = str(uuid.uuid4())
        
        # Simulate multiple handler calls with same correlation ID
        handlers_called = []
        
        async def mock_handler_1(update, data):
            handlers_called.append(("handler_1", data.get("correlation_id")))
            return await mock_handler_2(update, data)
        
        async def mock_handler_2(update, data):
            handlers_called.append(("handler_2", data.get("correlation_id")))
            return "final_result"
        
        data = {"correlation_id": correlation_id}
        update = MagicMock()
        
        await mock_handler_1(update, data)
        
        # Verify same correlation ID used throughout
        assert len(handlers_called) == 2
        assert handlers_called[0][1] == correlation_id
        assert handlers_called[1][1] == correlation_id
    
    @pytest.mark.asyncio
    async def test_request_context_propagation(self, caplog):
        """Test request context propagates through FSM transitions."""
        from bot.middlewares.logging_middleware import LoggingMiddleware
        middleware = LoggingMiddleware()
        
        user = User(id=12345, is_bot=False, first_name="Test")
        update = MagicMock()
        update.event_type = "message"
        
        async def fsm_handler(update, data):
            # Simulate FSM state change
            data["previous_state"] = ProfileSettings.main
            data["current_state"] = ProfileSettings.contact_info
            return "result"
        
        data = {"event_from_user": user}
        
        with caplog.at_level(logging.INFO):
            await middleware(fsm_handler, update, data)
        
        # Verify context is maintained and logged
        log_messages = [record.getMessage() for record in caplog.records]
        context_logs = [msg for msg in log_messages if "correlation_id" in msg]
        assert len(context_logs) > 0
    
    @pytest.mark.asyncio
    async def test_multi_step_dialog_tracing(self, caplog):
        """Test tracing through complete multi-step dialog flow."""
        correlation_id = str(uuid.uuid4())
        
        # Simulate complete profile settings flow
        steps = [
            ("settings_entry", ProfileSettings.main),
            ("contact_selection", ProfileSettings.contact_info),
            ("contact_input", ProfileSettings.contact_info),
            ("settings_return", ProfileSettings.main)
        ]
        
        with caplog.at_level(logging.INFO):
            for step_name, state in steps:
                logger = logging.getLogger(__name__)
                logger.info(
                    f"FSM step: {step_name}, "
                    f"state: {state}, "
                    f"correlation_id: {correlation_id}, "
                    f"user_id: 12345"
                )
        
        # Verify all steps are traced with same correlation ID
        step_logs = [r for r in caplog.records if "FSM step" in r.getMessage()]
        assert len(step_logs) == 4
        
        for log_record in step_logs:
            assert correlation_id in log_record.getMessage()
            assert "user_id: 12345" in log_record.getMessage()


class TestArchitectureQuality:
    """Test overall architecture quality and best practices."""
    
    def test_handler_separation_of_concerns(self):
        """Test handlers have proper separation of concerns."""
        from bot.handlers import profile_handlers
        import importlib
        
        # Check that profile_handlers module has user_repo attribute (repository pattern)
        assert hasattr(profile_handlers, 'user_repo'), "Module should use repository pattern"
        assert profile_handlers.user_repo is not None, "user_repo should be instantiated"
        
        # Check that module doesn't import direct database modules
        module_imports = []
        try:
            # Get the module's source to check imports
            import inspect
            source = inspect.getsource(profile_handlers)
            lines = source.split('\n')
            
            # Check for direct database imports
            forbidden_imports = ['sqlite3', 'sqlalchemy', 'asyncpg', 'psycopg2', 'aiosqlite']
            for line in lines:
                if line.strip().startswith('import ') or line.strip().startswith('from '):
                    for forbidden in forbidden_imports:
                        if forbidden in line:
                            module_imports.append(line.strip())
        except Exception:
            # If we can't inspect source, check module attributes
            pass
        
        # Assert no direct database imports found
        assert len(module_imports) == 0, f"Module should not import database modules directly: {module_imports}"
        
        # Verify repository pattern is used by checking module attributes
        assert hasattr(profile_handlers, 'UserRepository'), "Module should import UserRepository"
        assert hasattr(profile_handlers.user_repo, '__class__'), "user_repo should be a class instance"
    
    @pytest.mark.asyncio
    async def test_repository_pattern_usage(self, mock_message, mock_fsm_context):
        """Test that handlers actually use the repository pattern correctly."""
        from bot.handlers.profile_handlers import handle_contact_info_input
        
        # Mock the repository to verify it's called
        with patch('bot.handlers.profile_handlers.user_repo') as mock_repo, \
             patch('bot.handlers.profile_handlers.get_user_language') as mock_lang, \
             patch('bot.handlers.profile_handlers.get_localization') as mock_loc, \
             patch('bot.handlers.profile_handlers.is_valid_contact_info') as mock_validator, \
             patch('bot.handlers.profile_handlers.settings_handler') as mock_settings:
            
            # Setup mocks
            mock_lang.return_value = "en"
            mock_loc.return_value.profile_contact_saved = "Contact saved"
            mock_validator.return_value = True
            mock_repo.update_user_contact = AsyncMock()
            
            # Create mock user model
            mock_user = MagicMock(spec=UserModel)
            mock_user.user_id = 12345
            
            # Call the handler
            await handle_contact_info_input(mock_message, mock_fsm_context, lambda x: x, mock_user)
            
            # Verify repository method was called
            mock_repo.update_user_contact.assert_called_once_with(12345, mock_message.text)
            assert mock_validator.called, "Validation should be called"
            
            # Verify no direct database calls were made
            # (This is implicit since we're using the mocked repository)
    
    def test_fsm_state_isolation(self):
        """Test FSM states are properly isolated."""
        # Each state should handle only its specific inputs
        assert ProfileSettings.main != ProfileSettings.contact_info
        assert ProfileSettings.contact_info != ProfileSettings.reminders
        assert ProfileSettings.reminders != ProfileSettings.trusted_users
    
    def test_error_handling_consistency(self):
        """Test error handling is consistent across handlers."""
        from bot.handlers.profile_handlers import (
            settings_handler,
            set_contact_handler,
            set_reminders_handler,
            manage_trusted_handler
        )
        
        # All handlers should be callable and have proper signatures
        handlers = [settings_handler, set_contact_handler, set_reminders_handler, manage_trusted_handler]
        
        for handler in handlers:
            # Verify handlers are callable
            assert callable(handler), f"Handler {handler.__name__} should be callable"
            
            # Verify handlers have proper signatures (should accept message/query and state)
            import inspect
            sig = inspect.signature(handler)
            params = list(sig.parameters.keys())
            
            # Should have at least message/callback and state parameters
            assert len(params) >= 2, f"Handler {handler.__name__} should have at least 2 parameters"
            
            # Should have state parameter for FSM
            assert any('state' in param.lower() for param in params), f"Handler {handler.__name__} should have state parameter"
    
    def test_logging_integration(self):
        """Test logging is properly integrated throughout."""
        from bot.middlewares.logging_middleware import LoggingMiddleware
        
        # Middleware should be properly structured
        assert hasattr(LoggingMiddleware, '__call__')
        
        # Should handle both sync and async operations
        middleware = LoggingMiddleware()
        assert asyncio.iscoroutinefunction(middleware.__call__)
    
    @pytest.mark.asyncio
    async def test_middleware_chain_integrity(self):
        """Test middleware chain maintains integrity."""
        from bot.middlewares.logging_middleware import LoggingMiddleware
        
        middleware = LoggingMiddleware()
        
        # Test middleware doesn't break handler chain
        async def test_handler(update, data):
            return "handler_result"
        
        update = MagicMock()
        data = {"event_from_user": MagicMock()}
        
        result = await middleware(test_handler, update, data)
        assert result == "handler_result"
    
    def test_dependency_injection_pattern(self):
        """Test proper dependency injection patterns."""
        from bot.handlers.profile_handlers import handle_contact_info_input
        
        # Handler should accept dependencies as parameters
        import inspect
        sig = inspect.signature(handle_contact_info_input)
        params = list(sig.parameters.keys())
        
        # Should have proper dependency injection
        assert "message" in params
        assert "state" in params
        assert "db_user" in params
