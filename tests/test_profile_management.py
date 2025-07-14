"""Comprehensive tests for user profile management system."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from aiogram import types
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

# Mark all async tests in this module
pytestmark = pytest.mark.asyncio

from bot.handlers.profile_handlers import (
    ProfileSettings,
    settings_handler,
    set_contact_handler,
    handle_contact_info_input,
    set_reminders_handler,
    handle_reminders_input,
    manage_trusted_handler,
    trusted_add_handler,
    trusted_remove_handler,
    trusted_list_handler,
    handle_trusted_input,
    back_to_settings_handler,
)
from bot.db.models import User as UserModel
from bot.utils.validators import is_valid_contact_info, validate_username


class TestProfileSettings:
    """Test FSM states for profile settings."""

    def test_profile_settings_states_exist(self):
        """Test that all required FSM states are defined."""
        assert hasattr(ProfileSettings, 'main')
        assert hasattr(ProfileSettings, 'contact_info')
        assert hasattr(ProfileSettings, 'reminders')
        assert hasattr(ProfileSettings, 'trusted_users')


class TestSettingsHandler:
    """Test main settings handler functionality."""

    async def test_settings_handler_clears_state(self, model_message):
        """Test that settings handler clears existing FSM state."""
        message = model_message()
        message.answer = AsyncMock()
        state = AsyncMock(spec=FSMContext)
        
        with patch('bot.handlers.profile_handlers.get_user_language', return_value='en'), \
             patch('bot.handlers.profile_handlers.get_localization') as mock_loc, \
             patch('bot.handlers.profile_handlers.get_settings_menu_kb') as mock_kb, \
             patch('bot.handlers.profile_handlers.user_repo') as mock_repo:
            
            # Configure user repository mock
            mock_repo.get_or_create_user = AsyncMock(return_value=UserModel(
                user_id=123, first_name="John", username="john_doe"
            ))
            
            mock_loc.return_value.SETTINGS = "Settings Menu"
            mock_kb.return_value = InlineKeyboardMarkup(inline_keyboard=[])
            
            await settings_handler(message, state)
            
            state.clear.assert_called_once()
            message.answer.assert_called_once()

    async def test_settings_handler_displays_menu(self, model_message):
        """Test that settings handler displays the settings menu."""
        message = model_message()
        message.answer = AsyncMock()
        state = AsyncMock(spec=FSMContext)
        
        with patch('bot.handlers.profile_handlers.get_user_language', return_value='en'), \
             patch('bot.handlers.profile_handlers.get_localization') as mock_loc, \
             patch('bot.handlers.profile_handlers.get_settings_menu_kb') as mock_kb, \
             patch('bot.handlers.profile_handlers.user_repo') as mock_repo:
            
            # Configure user repository mock
            mock_repo.get_or_create_user = AsyncMock(return_value=UserModel(
                user_id=123, first_name="John", username="john_doe"
            ))
            
            mock_loc.return_value.SETTINGS = "Settings Menu"
            mock_keyboard = InlineKeyboardMarkup(inline_keyboard=[])
            mock_kb.return_value = mock_keyboard
            
            await settings_handler(message, state)
            
            message.answer.assert_called_once_with(
                text="Settings Menu",
                reply_markup=mock_keyboard
            )


class TestContactManagement:
    """Test contact information management functionality."""

    async def test_set_contact_handler_prompts_input(self, model_callback_query):
        """Test that contact handler prompts for contact info input."""
        callback = model_callback_query()
        callback.message.edit_text = AsyncMock()
        state = AsyncMock(spec=FSMContext)
        
        with patch('bot.handlers.profile_handlers.get_user_language', return_value='en'), \
             patch('bot.handlers.profile_handlers.get_localization') as mock_loc, \
             patch('bot.handlers.profile_handlers.back_to_settings_kb') as mock_kb, \
             patch('bot.handlers.profile_handlers.user_repo') as mock_repo:
            
            # Configure user repository mock
            mock_repo.get_or_create_user = AsyncMock(return_value=UserModel(
                user_id=123, first_name="John", username="john_doe"
            ))
            
            mock_loc.return_value.profile_contact_prompt = "Enter your contact info:"
            mock_keyboard = InlineKeyboardMarkup(inline_keyboard=[])
            mock_kb.return_value = mock_keyboard
            
            await set_contact_handler(callback, state)
            
            callback.message.edit_text.assert_called_once_with(
                text="Enter your contact info:",
                reply_markup=mock_keyboard
            )
            state.set_state.assert_called_once_with(ProfileSettings.contact_info)

    async def test_handle_contact_info_valid_input(self, model_message):
        """Test handling valid contact info input."""
        message = model_message(text="john@example.com")
        message.answer = AsyncMock()
        state = AsyncMock(spec=FSMContext)
        db_user = UserModel(
            user_id=123,
            first_name="John",
            username="john_doe"
        )
        
        with patch('bot.handlers.profile_handlers.get_user_language', return_value='en'), \
             patch('bot.handlers.profile_handlers.get_localization') as mock_loc, \
             patch('bot.handlers.profile_handlers.is_valid_contact_info', return_value=True), \
             patch('bot.handlers.profile_handlers.user_repo') as mock_repo, \
             patch('bot.handlers.profile_handlers.settings_handler', new_callable=AsyncMock) as mock_settings:
            
            # Configure all repository methods that might be called
            mock_repo.update_user_contact = AsyncMock()
            mock_repo.get_or_create_user = AsyncMock(return_value=db_user)
            mock_repo.get_by_id = AsyncMock(return_value=db_user)
            
            mock_loc.return_value.profile_contact_saved = "Contact info saved!"
            
            await handle_contact_info_input(message, state, lambda: None, db_user)
            
            mock_repo.update_user_contact.assert_called_once_with(123, "john@example.com")
            message.answer.assert_called_once_with("Contact info saved!")
            state.clear.assert_called_once()
            mock_settings.assert_called_once_with(message, state)

    async def test_handle_contact_info_invalid_input(self, model_message):
        """Test handling invalid contact info input."""
        message = model_message(text="<script>alert('xss')</script>")
        message.reply = AsyncMock()
        state = AsyncMock(spec=FSMContext)
        db_user = UserModel(
            user_id=123,
            first_name="John",
            username="john_doe"
        )
        
        with patch('bot.handlers.profile_handlers.get_user_language', return_value='en'), \
             patch('bot.handlers.profile_handlers.get_localization') as mock_loc, \
             patch('bot.handlers.profile_handlers.is_valid_contact_info', return_value=False), \
             patch('bot.handlers.profile_handlers.user_repo') as mock_repo:
            
            # Configure user repository mock even for invalid input case
            mock_repo.get_or_create_user = AsyncMock(return_value=db_user)
            
            mock_loc.return_value.profile_contact_invalid = "Invalid contact info!"
            
            await handle_contact_info_input(message, state, lambda: None, db_user)
            
            message.reply.assert_called_once_with("Invalid contact info!")

    def test_contact_validation_with_validators(self):
        """Test contact validation using validators module."""
        # Valid contact info
        assert is_valid_contact_info("john@example.com") == True
        assert is_valid_contact_info("+1234567890") == True
        assert is_valid_contact_info("Valid contact info") == True
        
        # Invalid contact info
        assert is_valid_contact_info("") == False
        assert is_valid_contact_info("   ") == False
        assert is_valid_contact_info("<script>") == False
        assert is_valid_contact_info("test>alert") == False


class TestReminderSettings:
    """Test reminder settings functionality."""

    async def test_set_reminders_handler_prompts_input(self, model_callback_query):
        """Test that reminders handler prompts for reminder settings."""
        callback = model_callback_query()
        callback.message.edit_text = AsyncMock()
        state = AsyncMock(spec=FSMContext)
        
        with patch('bot.handlers.profile_handlers.get_user_language', return_value='en'), \
             patch('bot.handlers.profile_handlers.get_localization') as mock_loc, \
             patch('bot.handlers.profile_handlers.back_to_settings_kb') as mock_kb, \
             patch('bot.handlers.profile_handlers.user_repo') as mock_repo:
            
            # Configure user repository mock
            mock_repo.get_or_create_user = AsyncMock(return_value=UserModel(
                user_id=123, first_name="John", username="john_doe"
            ))
            
            mock_loc.return_value.reminder_settings_prompt = "Enter payday days (1-31):"
            mock_keyboard = InlineKeyboardMarkup(inline_keyboard=[])
            mock_kb.return_value = mock_keyboard
            
            await set_reminders_handler(callback, state)
            
            callback.message.edit_text.assert_called_once_with(
                text="Enter payday days (1-31):",
                reply_markup=mock_keyboard
            )
            state.set_state.assert_called_once_with(ProfileSettings.reminders)

    async def test_handle_reminders_valid_single_day(self, model_message):
        """Test handling valid single reminder day."""
        message = model_message(text="15")
        message.answer = AsyncMock()
        state = AsyncMock(spec=FSMContext)
        db_user = UserModel(
            user_id=123,
            first_name="John",
            username="john_doe"
        )
        
        with patch('bot.handlers.profile_handlers.get_user_language', return_value='en'), \
             patch('bot.handlers.profile_handlers.get_localization') as mock_loc, \
             patch('bot.handlers.profile_handlers.user_repo') as mock_repo, \
             patch('bot.handlers.profile_handlers.settings_handler', new_callable=AsyncMock) as mock_settings:
            
            # Configure all repository methods that might be called
            mock_repo.update_user_reminders = AsyncMock()
            mock_repo.get_or_create_user = AsyncMock(return_value=db_user)
            mock_repo.get_by_id = AsyncMock(return_value=db_user)
            
            mock_loc.return_value.reminder_settings_saved = "Reminder settings saved!"
            
            await handle_reminders_input(message, state, lambda: None, db_user)
            
            mock_repo.update_user_reminders.assert_called_once_with(123, "15")
            message.answer.assert_called_once_with("Reminder settings saved!")
            state.clear.assert_called_once()

    async def test_handle_reminders_valid_multiple_days(self, model_message):
        """Test handling valid multiple reminder days."""
        message = model_message(text="1, 15, 30")
        message.answer = AsyncMock()
        state = AsyncMock(spec=FSMContext)
        db_user = UserModel(
            user_id=123,
            first_name="John",
            username="john_doe"
        )
        
        with patch('bot.handlers.profile_handlers.get_user_language', return_value='en'), \
             patch('bot.handlers.profile_handlers.get_localization') as mock_loc, \
             patch('bot.handlers.profile_handlers.user_repo') as mock_repo, \
             patch('bot.handlers.profile_handlers.settings_handler', new_callable=AsyncMock) as mock_settings:
            
            # Configure all repository methods that might be called
            mock_repo.update_user_reminders = AsyncMock()
            mock_repo.get_or_create_user = AsyncMock(return_value=db_user)
            mock_repo.get_by_id = AsyncMock(return_value=db_user)
            
            mock_loc.return_value.reminder_settings_saved = "Reminder settings saved!"
            
            await handle_reminders_input(message, state, lambda: None, db_user)
            
            mock_repo.update_user_reminders.assert_called_once_with(123, "1,15,30")

    async def test_handle_reminders_invalid_day_non_numeric(self, model_message):
        """Test handling invalid non-numeric reminder day."""
        message = model_message(text="abc")
        message.reply = AsyncMock()
        state = AsyncMock(spec=FSMContext)
        db_user = UserModel(
            user_id=123,
            first_name="John",
            username="john_doe"
        )
        
        with patch('bot.handlers.profile_handlers.get_user_language', return_value='en'), \
             patch('bot.handlers.profile_handlers.get_localization') as mock_loc, \
             patch('bot.handlers.profile_handlers.user_repo') as mock_repo:
            
            # Configure user repository mock even for invalid input case
            mock_repo.get_or_create_user = AsyncMock(return_value=db_user)
            
            mock_loc.return_value.reminder_invalid_day = "Invalid day! Use 1-31."
            
            await handle_reminders_input(message, state, lambda: None, db_user)
            
            message.reply.assert_called_once_with("Invalid day! Use 1-31.")

    async def test_handle_reminders_invalid_day_out_of_range(self, model_message):
        """Test handling invalid out-of-range reminder day."""
        message = model_message(text="32")
        message.reply = AsyncMock()
        state = AsyncMock(spec=FSMContext)
        db_user = UserModel(
            user_id=123,
            first_name="John",
            username="john_doe"
        )
        
        with patch('bot.handlers.profile_handlers.get_user_language', return_value='en'), \
             patch('bot.handlers.profile_handlers.get_localization') as mock_loc, \
             patch('bot.handlers.profile_handlers.user_repo') as mock_repo:
            
            # Configure user repository mock even for invalid input case
            mock_repo.get_or_create_user = AsyncMock(return_value=db_user)
            
            mock_loc.return_value.reminder_invalid_day = "Invalid day! Use 1-31."
            
            await handle_reminders_input(message, state, lambda: None, db_user)
            
            message.reply.assert_called_once_with("Invalid day! Use 1-31.")


class TestTrustedUsersManagement:
    """Test trusted users management functionality."""

    async def test_manage_trusted_handler_shows_menu(self, model_callback_query):
        """Test that manage trusted handler shows management menu."""
        callback = model_callback_query()
        callback.message.edit_text = AsyncMock()
        state = AsyncMock(spec=FSMContext)
        
        with patch('bot.handlers.profile_handlers.get_user_language', return_value='en'), \
             patch('bot.handlers.profile_handlers.get_localization') as mock_loc, \
             patch('bot.handlers.profile_handlers.user_repo') as mock_repo:
            
            # Configure user repository mock
            mock_repo.get_or_create_user = AsyncMock(return_value=UserModel(
                user_id=123, first_name="John", username="john_doe"
            ))
            
            mock_loc.return_value.trusted_user_add_prompt = "Add trusted user"
            mock_loc.return_value.trusted_user_remove_prompt = "Remove trusted user"
            mock_loc.return_value.trusted_user_list_title = "Trusted users"
            mock_loc.return_value.generic_back = "Back"
            
            await manage_trusted_handler(callback, state)
            
            callback.message.edit_text.assert_called_once()
            state.set_state.assert_called_once_with(ProfileSettings.trusted_users)
            state.update_data.assert_called_once_with(action=None)

    async def test_trusted_add_handler_prompts_username(self, model_callback_query):
        """Test that add trusted handler prompts for username."""
        callback = model_callback_query()
        callback.message.edit_text = AsyncMock()
        state = AsyncMock(spec=FSMContext)
        
        with patch('bot.handlers.profile_handlers.get_user_language', return_value='en'), \
             patch('bot.handlers.profile_handlers.get_localization') as mock_loc, \
             patch('bot.handlers.profile_handlers.user_repo') as mock_repo:
            
            # Configure user repository mock
            mock_repo.get_or_create_user = AsyncMock(return_value=UserModel(
                user_id=123, first_name="John", username="john_doe"
            ))
            
            mock_loc.return_value.trusted_user_add_prompt = "Enter username to trust:"
            mock_loc.return_value.generic_cancel = "Cancel"
            
            await trusted_add_handler(callback, state)
            
            callback.message.edit_text.assert_called_once()
            state.set_state.assert_called_once_with(ProfileSettings.trusted_users)
            state.update_data.assert_called_once_with(action="add")

    async def test_trusted_remove_handler_prompts_username(self, model_callback_query):
        """Test that remove trusted handler prompts for username."""
        callback = model_callback_query()
        callback.message.edit_text = AsyncMock()
        state = AsyncMock(spec=FSMContext)
        
        with patch('bot.handlers.profile_handlers.get_user_language', return_value='en'), \
             patch('bot.handlers.profile_handlers.get_localization') as mock_loc, \
             patch('bot.handlers.profile_handlers.user_repo') as mock_repo:
            
            # Configure user repository mock
            mock_repo.get_or_create_user = AsyncMock(return_value=UserModel(
                user_id=123, first_name="John", username="john_doe"
            ))
            
            mock_loc.return_value.trusted_user_remove_prompt = "Enter username to remove:"
            mock_loc.return_value.generic_cancel = "Cancel"
            
            await trusted_remove_handler(callback, state)
            
            callback.message.edit_text.assert_called_once()
            state.set_state.assert_called_once_with(ProfileSettings.trusted_users)
            state.update_data.assert_called_once_with(action="remove")

    async def test_trusted_list_handler_empty_list(self, model_callback_query):
        """Test trusted list handler with empty list."""
        callback = model_callback_query()
        callback.message.edit_text = AsyncMock()
        state = AsyncMock(spec=FSMContext)
        db_user = UserModel(
            user_id=123,
            first_name="John",
            username="john_doe"
        )
        
        with patch('bot.handlers.profile_handlers.get_user_language', return_value='en'), \
             patch('bot.handlers.profile_handlers.get_localization') as mock_loc, \
             patch('bot.handlers.profile_handlers.user_repo') as mock_repo, \
             patch('bot.handlers.profile_handlers.back_to_settings_kb') as mock_kb:
            
            # Configure all repository methods that might be called
            mock_repo.list_trusted = AsyncMock(return_value=[])
            mock_repo.get_or_create_user = AsyncMock(return_value=db_user)
            mock_repo.get_by_id = AsyncMock(return_value=db_user)
            
            mock_loc.return_value.trusted_user_list_empty = "No trusted users"
            mock_keyboard = InlineKeyboardMarkup(inline_keyboard=[])
            mock_kb.return_value = mock_keyboard
            
            await trusted_list_handler(callback, state, db_user)
            
            callback.message.edit_text.assert_called_once_with(
                text="No trusted users",
                reply_markup=mock_keyboard
            )
            state.clear.assert_called_once()

    async def test_trusted_list_handler_with_users(self, model_callback_query):
        """Test trusted list handler with existing trusted users."""
        callback = model_callback_query()
        callback.message.edit_text = AsyncMock()
        state = AsyncMock(spec=FSMContext)
        db_user = UserModel(
            user_id=123,
            first_name="John",
            username="john_doe"
        )
        
        with patch('bot.handlers.profile_handlers.get_user_language', return_value='en'), \
             patch('bot.handlers.profile_handlers.get_localization') as mock_loc, \
             patch('bot.handlers.profile_handlers.user_repo') as mock_repo, \
             patch('bot.handlers.profile_handlers.back_to_settings_kb') as mock_kb:
            
            # Configure all repository methods that might be called
            mock_repo.list_trusted = AsyncMock(return_value=["alice", "bob"])
            mock_repo.get_or_create_user = AsyncMock(return_value=db_user)
            mock_repo.get_by_id = AsyncMock(return_value=db_user)
            
            mock_loc.return_value.trusted_user_list_title = "Trusted users:"
            mock_keyboard = InlineKeyboardMarkup(inline_keyboard=[])
            mock_kb.return_value = mock_keyboard
            
            await trusted_list_handler(callback, state, db_user)
            
            expected_text = "Trusted users:\n- alice\n- bob"
            callback.message.edit_text.assert_called_once_with(
                text=expected_text,
                reply_markup=mock_keyboard
            )

    async def test_handle_trusted_input_add_new_user(self, model_message):
        """Test adding a new trusted user."""
        message = model_message(text="@alice")
        message.answer = AsyncMock()
        state = AsyncMock(spec=FSMContext)
        state.get_data = AsyncMock(return_value={"action": "add"})
        db_user = UserModel(
            user_id=123,
            first_name="John",
            username="john_doe"
        )
        
        with patch('bot.handlers.profile_handlers.get_user_language', return_value='en'), \
             patch('bot.handlers.profile_handlers.get_localization') as mock_loc, \
             patch('bot.handlers.profile_handlers.validate_username', return_value="alice"), \
             patch('bot.handlers.profile_handlers.user_repo') as mock_repo, \
             patch('bot.handlers.profile_handlers.settings_handler', new_callable=AsyncMock) as mock_settings:
            
            # Configure all repository methods that might be called
            mock_repo.trusts = AsyncMock(return_value=False)
            mock_repo.add_trust = AsyncMock()
            mock_repo.get_or_create_user = AsyncMock(return_value=db_user)
            mock_repo.get_by_id = AsyncMock(return_value=db_user)
            mock_repo.get_by_username = AsyncMock(return_value=UserModel(
                user_id=456, first_name="Alice", username="alice"
            ))
            
            mock_loc.return_value.trusted_user_add_success = "Added {username} to trusted users!"
            
            await handle_trusted_input(message, state, lambda: None, db_user)
            
            mock_repo.add_trust.assert_called_once_with(123, "alice")
            message.answer.assert_called_once_with("Added alice to trusted users!")
            state.clear.assert_called_once()

    async def test_handle_trusted_input_add_existing_user(self, model_message):
        """Test adding an already trusted user."""
        message = model_message(text="@alice")
        message.answer = AsyncMock()
        state = AsyncMock(spec=FSMContext)
        state.get_data = AsyncMock(return_value={"action": "add"})
        db_user = UserModel(
            user_id=123,
            first_name="John",
            username="john_doe"
        )
        
        with patch('bot.handlers.profile_handlers.get_user_language', return_value='en'), \
             patch('bot.handlers.profile_handlers.get_localization') as mock_loc, \
             patch('bot.handlers.profile_handlers.validate_username', return_value="alice"), \
             patch('bot.handlers.profile_handlers.user_repo') as mock_repo:
            
            # Configure all repository methods that might be called
            mock_repo.trusts = AsyncMock(return_value=True)
            mock_repo.get_or_create_user = AsyncMock(return_value=db_user)
            mock_repo.get_by_username = AsyncMock(return_value=UserModel(
                user_id=456, first_name="Alice", username="alice"
            ))
            
            mock_loc.return_value.trusted_user_add_exists = "{username} is already trusted!"
            
            await handle_trusted_input(message, state, lambda: None, db_user)
            
            message.answer.assert_called_once_with("alice is already trusted!")

    async def test_handle_trusted_input_remove_existing_user(self, model_message):
        """Test removing an existing trusted user."""
        message = model_message(text="@alice")
        message.answer = AsyncMock()
        state = AsyncMock(spec=FSMContext)
        state.get_data = AsyncMock(return_value={"action": "remove"})
        db_user = UserModel(
            user_id=123,
            first_name="John",
            username="john_doe"
        )
        
        with patch('bot.handlers.profile_handlers.get_user_language', return_value='en'), \
             patch('bot.handlers.profile_handlers.get_localization') as mock_loc, \
             patch('bot.handlers.profile_handlers.validate_username', return_value="alice"), \
             patch('bot.handlers.profile_handlers.user_repo') as mock_repo, \
             patch('bot.handlers.profile_handlers.settings_handler', new_callable=AsyncMock) as mock_settings:
            
            # Configure all repository methods that might be called
            mock_repo.trusts = AsyncMock(return_value=True)
            mock_repo.remove_trust = AsyncMock()
            mock_repo.get_or_create_user = AsyncMock(return_value=db_user)
            mock_repo.get_by_username = AsyncMock(return_value=UserModel(
                user_id=456, first_name="Alice", username="alice"
            ))
            
            mock_loc.return_value.trusted_user_remove_success = "Removed {username} from trusted users!"
            
            await handle_trusted_input(message, state, lambda: None, db_user)
            
            mock_repo.remove_trust.assert_called_once_with(123, "alice")
            message.answer.assert_called_once_with("Removed alice from trusted users!")
            state.clear.assert_called_once()

    async def test_handle_trusted_input_invalid_username(self, model_message):
        """Test handling invalid username format."""
        message = model_message(text="invalid_username")
        message.reply = AsyncMock()
        state = AsyncMock(spec=FSMContext)
        state.get_data = AsyncMock(return_value={"action": "add"})
        db_user = UserModel(
            user_id=123,
            first_name="John",
            username="john_doe"
        )
        
        with patch('bot.handlers.profile_handlers.get_user_language', return_value='en'), \
             patch('bot.handlers.profile_handlers.get_localization') as mock_loc, \
             patch('bot.handlers.profile_handlers.validate_username', side_effect=ValueError("Invalid format")), \
             patch('bot.handlers.profile_handlers.user_repo') as mock_repo:
            
            # Configure user repository mock even for invalid input case
            mock_repo.get_or_create_user = AsyncMock(return_value=db_user)
            
            mock_loc.return_value.error_validation = "Validation error: {details}"
            mock_loc.return_value.trusted_user_add_prompt = "Enter valid username"
            
            await handle_trusted_input(message, state, lambda: None, db_user)
            
            message.reply.assert_called_once_with("Validation error: Enter valid username")

    def test_username_validation_with_validators(self):
        """Test username validation using validators module."""
        # Valid usernames
        assert validate_username("@alice") == "alice"
        assert validate_username("alice") == "alice"
        assert validate_username("@user_123") == "user_123"
        
        # Invalid usernames
        with pytest.raises(ValueError):
            validate_username("@ab")  # Too short
        with pytest.raises(ValueError):
            validate_username("@" + "a" * 33)  # Too long
        with pytest.raises(ValueError):
            validate_username("@user-name")  # Invalid character


class TestFSMStateTransitions:
    """Test FSM state transitions and error handling."""

    async def test_back_to_settings_handler_clears_state(self, model_callback_query):
        """Test that back to settings handler clears FSM state."""
        callback = model_callback_query()
        callback.message.edit_text = AsyncMock()
        state = AsyncMock(spec=FSMContext)
        
        with patch('bot.handlers.profile_handlers.get_user_language', return_value='en'), \
             patch('bot.handlers.profile_handlers.get_localization') as mock_loc, \
             patch('bot.handlers.profile_handlers.get_settings_menu_kb') as mock_kb, \
             patch('bot.handlers.profile_handlers.user_repo') as mock_repo:
            
            # Configure user repository mock
            mock_repo.get_or_create_user = AsyncMock(return_value=UserModel(
                user_id=123, first_name="John", username="john_doe"
            ))
            
            mock_loc.return_value.SETTINGS = "Settings Menu"
            mock_keyboard = InlineKeyboardMarkup(inline_keyboard=[])
            mock_kb.return_value = mock_keyboard
            
            await back_to_settings_handler(callback, state)
            
            state.clear.assert_called_once()
            callback.message.edit_text.assert_called_once_with(
                text="Settings Menu",
                reply_markup=mock_keyboard
            )

    async def test_fsm_state_persistence_across_interactions(self, model_callback_query):
        """Test that FSM state persists correctly across multiple interactions."""
        state = AsyncMock(spec=FSMContext)
        
        # Simulate entering contact info state
        callback = model_callback_query()
        callback.message.edit_text = AsyncMock()
        
        with patch('bot.handlers.profile_handlers.get_user_language', return_value='en'), \
             patch('bot.handlers.profile_handlers.get_localization') as mock_loc, \
             patch('bot.handlers.profile_handlers.back_to_settings_kb'), \
             patch('bot.handlers.profile_handlers.user_repo') as mock_repo:
            
            # Configure user repository mock
            mock_repo.get_or_create_user = AsyncMock(return_value=UserModel(
                user_id=123, first_name="John", username="john_doe"
            ))
            
            mock_loc.return_value.profile_contact_prompt = "Enter contact:"
            
            await set_contact_handler(callback, state)
            
            # Verify state was set
            state.set_state.assert_called_once_with(ProfileSettings.contact_info)


class TestProfileDataPersistence:
    """Test profile data persistence and database integration."""

    async def test_contact_info_persistence(self, model_message):
        """Test that contact info is properly saved to database."""
        message = model_message(text="john@example.com")
        message.answer = AsyncMock()
        state = AsyncMock(spec=FSMContext)
        db_user = UserModel(
            user_id=123,
            first_name="John",
            username="john_doe"
        )
        
        with patch('bot.handlers.profile_handlers.get_user_language', return_value='en'), \
             patch('bot.handlers.profile_handlers.get_localization') as mock_loc, \
             patch('bot.handlers.profile_handlers.is_valid_contact_info', return_value=True), \
             patch('bot.handlers.profile_handlers.user_repo') as mock_repo, \
             patch('bot.handlers.profile_handlers.settings_handler', new_callable=AsyncMock):
            
            # Configure all repository methods that might be called
            mock_repo.update_user_contact = AsyncMock()
            mock_repo.get_or_create_user = AsyncMock(return_value=db_user)
            mock_repo.get_by_id = AsyncMock(return_value=db_user)
            
            mock_loc.return_value.profile_contact_saved = "Saved!"
            
            await handle_contact_info_input(message, state, lambda: None, db_user)
            
            # Verify database update was called with correct parameters
            mock_repo.update_user_contact.assert_called_once_with(123, "john@example.com")

    async def test_reminder_settings_persistence(self, model_message):
        """Test that reminder settings are properly saved to database."""
        message = model_message(text="1,15,30")
        message.answer = AsyncMock()
        state = AsyncMock(spec=FSMContext)
        db_user = UserModel(
            user_id=123,
            first_name="John",
            username="john_doe"
        )
        
        with patch('bot.handlers.profile_handlers.get_user_language', return_value='en'), \
             patch('bot.handlers.profile_handlers.get_localization') as mock_loc, \
             patch('bot.handlers.profile_handlers.user_repo') as mock_repo, \
             patch('bot.handlers.profile_handlers.settings_handler', new_callable=AsyncMock):
            
            # Configure all repository methods that might be called
            mock_repo.update_user_reminders = AsyncMock()
            mock_repo.get_or_create_user = AsyncMock(return_value=db_user)
            mock_repo.get_by_id = AsyncMock(return_value=db_user)
            
            mock_loc.return_value.reminder_settings_saved = "Saved!"
            
            await handle_reminders_input(message, state, lambda: None, db_user)
            
            # Verify database update was called with correct parameters
            mock_repo.update_user_reminders.assert_called_once_with(123, "1,15,30")

    async def test_trusted_users_persistence(self, model_message):
        """Test that trusted user relationships are properly saved to database."""
        message = model_message(text="@alice")
        message.answer = AsyncMock()
        state = AsyncMock(spec=FSMContext)
        state.get_data = AsyncMock(return_value={"action": "add"})
        db_user = UserModel(
            user_id=123,
            first_name="John",
            username="john_doe"
        )
        
        with patch('bot.handlers.profile_handlers.get_user_language', return_value='en'), \
             patch('bot.handlers.profile_handlers.get_localization') as mock_loc, \
             patch('bot.handlers.profile_handlers.validate_username', return_value="alice"), \
             patch('bot.handlers.profile_handlers.user_repo') as mock_repo, \
             patch('bot.handlers.profile_handlers.settings_handler', new_callable=AsyncMock):
            
            # Configure all repository methods that might be called
            mock_repo.trusts = AsyncMock(return_value=False)
            mock_repo.add_trust = AsyncMock()
            mock_repo.get_or_create_user = AsyncMock(return_value=db_user)
            mock_repo.get_by_username = AsyncMock(return_value=UserModel(
                user_id=456, first_name="Alice", username="alice"
            ))
            
            mock_loc.return_value.trusted_user_add_success = "Added!"
            
            await handle_trusted_input(message, state, lambda: None, db_user)
            
            # Verify database operations were called correctly
            mock_repo.trusts.assert_called_once_with(123, "alice")
            mock_repo.add_trust.assert_called_once_with(123, "alice")


class TestErrorHandling:
    """Test error handling and edge cases."""

    async def test_handle_none_message_text(self, model_message):
        """Test handling of None message text."""
        message = model_message(text=None)
        message.reply = AsyncMock()
        state = AsyncMock(spec=FSMContext)
        db_user = UserModel(
            user_id=123,
            first_name="John",
            username="john_doe"
        )
        
        with patch('bot.handlers.profile_handlers.get_user_language', return_value='en'), \
             patch('bot.handlers.profile_handlers.get_localization') as mock_loc, \
             patch('bot.handlers.profile_handlers.user_repo') as mock_repo:
            
            # Configure user repository mock even for error case
            mock_repo.get_or_create_user = AsyncMock(return_value=db_user)
            
            mock_loc.return_value.profile_contact_invalid = "Invalid input!"
            
            await handle_contact_info_input(message, state, lambda: None, db_user)
            
            # Should handle None text gracefully
            message.reply.assert_called_once_with("Invalid input!")

    async def test_handle_empty_reminder_input(self, model_message):
        """Test handling of empty reminder input."""
        message = model_message(text="   ")
        message.answer = AsyncMock()
        state = AsyncMock(spec=FSMContext)
        db_user = UserModel(
            user_id=123,
            first_name="John",
            username="john_doe"
        )
        
        with patch('bot.handlers.profile_handlers.get_user_language', return_value='en'), \
             patch('bot.handlers.profile_handlers.get_localization') as mock_loc, \
             patch('bot.handlers.profile_handlers.user_repo') as mock_repo, \
             patch('bot.handlers.profile_handlers.settings_handler', new_callable=AsyncMock):
            
            # Configure all repository methods that might be called
            mock_repo.update_user_reminders = AsyncMock()
            mock_repo.get_or_create_user = AsyncMock(return_value=db_user)
            mock_repo.get_by_id = AsyncMock(return_value=db_user)
            
            mock_loc.return_value.reminder_settings_saved = "Saved!"
            
            await handle_reminders_input(message, state, lambda: None, db_user)
            
            # Should save empty string for no reminders
            mock_repo.update_user_reminders.assert_called_once_with(123, "")

    async def test_handle_unknown_trusted_action(self, model_message):
        """Test handling of unknown trusted user action."""
        message = model_message(text="@alice")
        message.reply = AsyncMock()
        state = AsyncMock(spec=FSMContext)
        state.get_data = AsyncMock(return_value={"action": "unknown"})
        db_user = UserModel(
            user_id=123,
            first_name="John",
            username="john_doe"
        )
        
        with patch('bot.handlers.profile_handlers.get_user_language', return_value='en'), \
             patch('bot.handlers.profile_handlers.get_localization') as mock_loc, \
             patch('bot.handlers.profile_handlers.validate_username', return_value="alice"), \
             patch('bot.handlers.profile_handlers.settings_handler', new_callable=AsyncMock), \
             patch('bot.handlers.profile_handlers.user_repo') as mock_repo:
            
            # Configure user repository mock even for error case
            mock_repo.get_or_create_user = AsyncMock(return_value=db_user)
            
            mock_loc.return_value.fsm_invalid_state = "Invalid state!"
            
            await handle_trusted_input(message, state, lambda: None, db_user)
            
            message.reply.assert_called_once_with("Invalid state!")


class TestIntegrationWithRepositories:
    """Test integration between profile handlers and database repositories."""

    async def test_user_repo_integration_contact_update(self, model_message):
        """Test integration with user repository for contact updates."""
        with patch('bot.handlers.profile_handlers.user_repo') as mock_repo:
            # Configure all repository methods that might be called
            mock_repo.update_user_contact = AsyncMock()
            mock_repo.get_or_create_user = AsyncMock()
            mock_repo.get_by_id = AsyncMock()
            
            message = model_message(text="test@example.com")
            message.answer = AsyncMock()
            state = AsyncMock(spec=FSMContext)
            db_user = UserModel(user_id=123, first_name="John", username="john_doe")
            
            with patch('bot.handlers.profile_handlers.get_user_language', return_value='en'), \
                 patch('bot.handlers.profile_handlers.get_localization') as mock_loc, \
                 patch('bot.handlers.profile_handlers.is_valid_contact_info', return_value=True), \
                 patch('bot.handlers.profile_handlers.settings_handler', new_callable=AsyncMock):
                
                mock_loc.return_value.profile_contact_saved = "Saved!"
                
                await handle_contact_info_input(message, state, lambda: None, db_user)
                
                # Verify repository method was called
                mock_repo.update_user_contact.assert_called_once_with(123, "test@example.com")

    async def test_user_repo_integration_trusted_users(self, model_callback_query):
        """Test integration with user repository for trusted user operations."""
        with patch('bot.handlers.profile_handlers.user_repo') as mock_repo:
            # Configure all repository methods that might be called
            mock_repo.trusts = AsyncMock(return_value=False)
            mock_repo.add_trust = AsyncMock()
            mock_repo.list_trusted = AsyncMock(return_value=["alice", "bob"])
            mock_repo.update_user_contact = AsyncMock()
            mock_repo.update_user_reminders = AsyncMock()
            mock_repo.remove_trust = AsyncMock()
            mock_repo.get_or_create_user = AsyncMock()
            mock_repo.get_by_id = AsyncMock()
            mock_repo.get_by_username = AsyncMock()
            
            # Test list operation
            callback = model_callback_query()
            callback.message.edit_text = AsyncMock()
            state = AsyncMock(spec=FSMContext)
            db_user = UserModel(user_id=123, first_name="John", username="john_doe")
            
            with patch('bot.handlers.profile_handlers.get_user_language', return_value='en'), \
                 patch('bot.handlers.profile_handlers.get_localization') as mock_loc, \
                 patch('bot.handlers.profile_handlers.back_to_settings_kb'):
                
                mock_loc.return_value.trusted_user_list_title = "Trusted users:"
                
                await trusted_list_handler(callback, state, db_user)
                
                # Verify repository method was called
                mock_repo.list_trusted.assert_called_once_with(123)
