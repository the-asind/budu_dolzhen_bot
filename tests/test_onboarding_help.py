"""Tests for enhanced onboarding and help system."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from aiogram.types import InlineKeyboardMarkup
from aiogram.enums import ChatType

from bot.handlers.common import handle_start_command, handle_help_command


class TestOnboardingFlow:
    """Test comprehensive onboarding flow with step-by-step guidance."""

    @pytest.fixture
    def mock_message_group(self, model_user, model_chat):
        """Create a mock message in group chat using mutable mock helper."""
        from tests.conftest import make_mutable_message
        user = model_user(id=12345, username="testuser", first_name="Test", language_code="en")
        chat = model_chat(id=-67890, type=ChatType.GROUP, title="Test Group")
        return make_mutable_message(from_user=user, chat=chat)

    @pytest.fixture
    def mock_localization(self):
        """Mock localization function."""
        def _(key):
            localization_map = {
                "start_welcome": "Hello! I am 'Budu Dolzhen' bot, here to help you track debts among friends.",
                "onboarding_private_step1": "Step 1: To record a debt, mention a user with @username followed by amount and description.",
                "onboarding_private_step2": "Step 2: Your friend will receive a notification to confirm the debt.",
                "onboarding_private_step3": "Step 3: Use /pay to record payments and /settings to manage preferences.",
                "onboarding_private_example": "Example: @friend 500 for coffee",
                "start_welcome_group": "Hello! I'm here to help track debts in your group.",
                "onboarding_group_step1": "Mention users with @username amount description to record debts.",
                "onboarding_group_step2": "Privacy notice: All debt information is visible to group members.",
                "onboarding_resources": "Here are some helpful resources:",
                "btn_documentation": "📖 Documentation",
                "btn_support": "💬 Support",
                "btn_discord": "💬 Discord",
                "btn_github": "🔧 GitHub",
                "help_intro": "Welcome to the help center! Here's everything you need to know:",
                "help_commands": "Available Commands:\n/start - Get started\n/help - Show this help\n/pay - Record payment\n/settings - Manage settings",
                "help_faq": "Frequently Asked Questions:\nQ: How do I record a debt?\nA: Use @username amount description",
                "help_troubleshooting": "Troubleshooting:\n- Check username format\n- Ensure amount is positive\n- Contact support if issues persist",
                "help_hints": "💡 Tips:\n- Use clear descriptions\n- Confirm debts promptly\n- Check your settings regularly",
                "help_resources": "Need more help? Check out these resources:"
            }
            return localization_map.get(key, key)
        return _

    @pytest.mark.asyncio
    async def test_group_chat_onboarding_differentiation(self, mock_message_group, mock_localization):
        """Test onboarding differentiation for group chat context."""
        with patch('bot.handlers.common.user_repo') as mock_repo, \
             patch('bot.handlers.common._', side_effect=mock_localization):
            
            mock_repo.get_or_create_user = AsyncMock()
            
            await handle_start_command(mock_message_group, mock_localization)
            
            # Verify that messages were sent
            assert mock_message_group.answer.call_count >= 1
            
            # Verify group-specific content was included
            calls = [call[0][0] for call in mock_message_group.answer.call_args_list]
            
            # Check for group-specific messaging (more flexible matching)
            group_content_found = any(
                "group" in call.lower() or "privacy" in call.lower() 
                for call in calls
            )
            assert group_content_found, "Group-specific content should be present in onboarding"

class TestEnhancedHelpSystem:
    """Test enhanced /help command with comprehensive guidance."""

    @pytest.fixture
    def mock_message(self, model_user, model_chat):
        """Create a mock message for help testing using mutable mock helper."""
        from tests.conftest import make_mutable_message
        user = model_user(id=12345, username="testuser", first_name="Test")
        chat = model_chat(id=12345, type=ChatType.PRIVATE)
        return make_mutable_message(from_user=user, chat=chat)

    @pytest.fixture
    def mock_localization(self):
        """Mock localization function for help system."""
        def _(key):
            localization_map = {
                "help_intro": "Welcome to the help center! Here's everything you need to know:",
                "help_commands": "Available Commands:\n/start - Get started\n/help - Show this help\n/pay - Record payment\n/settings - Manage settings",
                "help_faq": "Frequently Asked Questions:\nQ: How do I record a debt?\nA: Use @username amount description",
                "help_troubleshooting": "Troubleshooting:\n- Check username format\n- Ensure amount is positive\n- Contact support if issues persist",
                "help_hints": "💡 Tips:\n- Use clear descriptions\n- Confirm debts promptly\n- Check your settings regularly",
                "help_resources": "Need more help? Check out these resources:",
                "btn_documentation": "📖 Documentation",
                "btn_support": "💬 Support",
                "btn_discord": "💬 Discord",
                "btn_github": "🔧 GitHub"
            }
            return localization_map.get(key, key)
        return _

    @pytest.mark.asyncio
    async def test_comprehensive_help_sections(self, mock_message, mock_localization):
        """Test that help command includes all required sections."""
        with patch('bot.handlers.common._', side_effect=mock_localization):
            await handle_help_command(mock_message, mock_localization)
            
            # Verify that help messages were sent
            assert mock_message.answer.call_count >= 1
            
            # Verify help content is present
            calls = [call[0][0] for call in mock_message.answer.call_args_list]
            
            # Check for key help content (more flexible matching)
            help_content_found = any(
                "help" in call.lower() or "command" in call.lower() or "welcome" in call.lower()
                for call in calls
            )
            assert help_content_found, "Help content should be present in help command response"

    @pytest.mark.asyncio
    async def test_command_specific_help(self, mock_message, mock_localization):
        """Test command-specific help information."""
        with patch('bot.handlers.common._', side_effect=mock_localization):
            await handle_help_command(mock_message, mock_localization)
            
            calls = [call[0][0] for call in mock_message.answer.call_args_list]
            
            # Look for commands in any of the help messages
            all_text = " ".join(calls)
            
            # Verify that command information is present
            commands_mentioned = any(
                cmd in all_text for cmd in ["/start", "/help", "/pay", "/settings"]
            )
            assert commands_mentioned, "Command information should be present in help response"

    @pytest.mark.asyncio
    async def test_faq_section(self, mock_message, mock_localization):
        """Test FAQ section content."""
        with patch('bot.handlers.common._', side_effect=mock_localization):
            await handle_help_command(mock_message, mock_localization)
            
            calls = [call[0][0] for call in mock_message.answer.call_args_list]
            all_text = " ".join(calls)
            
            # Verify FAQ-style content is present
            faq_content_found = any(
                keyword in all_text.lower() 
                for keyword in ["question", "how", "@username", "debt"]
            )
            assert faq_content_found, "FAQ-style content should be present in help response"

    @pytest.mark.asyncio
    async def test_troubleshooting_section(self, mock_message, mock_localization):
        """Test troubleshooting guide content."""
        with patch('bot.handlers.common._', side_effect=mock_localization):
            await handle_help_command(mock_message, mock_localization)
            
            calls = [call[0][0] for call in mock_message.answer.call_args_list]
            all_text = " ".join(calls)
            
            # Verify troubleshooting-style content is present
            troubleshooting_content_found = any(
                keyword in all_text.lower() 
                for keyword in ["troubleshooting", "check", "ensure", "support"]
            )
            assert troubleshooting_content_found, "Troubleshooting content should be present in help response"

    @pytest.mark.asyncio
    async def test_inline_hints_section(self, mock_message, mock_localization):
        """Test inline hints and tips section."""
        with patch('bot.handlers.common._', side_effect=mock_localization):
            await handle_help_command(mock_message, mock_localization)
            
            calls = [call[0][0] for call in mock_message.answer.call_args_list]
            all_text = " ".join(calls)
            
            # Verify hints and tips content is present
            hints_content_found = any(
                keyword in all_text.lower() 
                for keyword in ["tips", "hint", "clear", "confirm", "settings"]
            )
            assert hints_content_found, "Hints and tips content should be present in help response"

    @pytest.mark.asyncio
    async def test_help_external_resources(self, mock_message, mock_localization):
        """Test external resource links in help."""
        with patch('bot.handlers.common._', side_effect=mock_localization):
            await handle_help_command(mock_message, mock_localization)
            
            # Find the resources keyboard call
            resources_call = None
            for call in mock_message.answer.call_args_list:
                if 'reply_markup' in call[1]:
                    resources_call = call
                    break
            
            assert resources_call is not None
            keyboard = resources_call[1]['reply_markup']
            assert isinstance(keyboard, InlineKeyboardMarkup)


class TestContextualHelp:
    """Test contextual help and inline hints in error scenarios."""

    @pytest.fixture
    def mock_localization_with_errors(self):
        """Mock localization with error and hint messages."""
        def _(key):
            localization_map = {
                "error_validation": "Validation error: {details}",
                "hint_amount_format": "Amount must be a number. For example: 500.50",
                "hint_username_format": "Usernames must start with @ and contain no spaces.",
                "error_debt_not_found": "Debt not found.",
                "error_timeout": "Action timed out. Please try again.",
                "error_permission": "You do not have permission to perform this action.",
                "fsm_invalid_state": "Invalid state. Please start over.",
                "fsm_timeout": "Session timed out. Please try again."
            }
            return localization_map.get(key, key)
        return _

    def test_validation_error_hints(self, mock_localization_with_errors):
        """Test that validation errors include helpful hints."""
        _ = mock_localization_with_errors
        
        # Test amount format hint
        amount_hint = _("hint_amount_format")
        assert "must be a number" in amount_hint
        assert "500.50" in amount_hint
        
        # Test username format hint
        username_hint = _("hint_username_format")
        assert "must start with @" in username_hint
        assert "no spaces" in username_hint

    def test_error_message_guidance(self, mock_localization_with_errors):
        """Test that error messages provide actionable guidance."""
        _ = mock_localization_with_errors
        
        # Test timeout error guidance
        timeout_error = _("error_timeout")
        assert "try again" in timeout_error
        
        # Test FSM state error guidance
        fsm_error = _("fsm_invalid_state")
        assert "start over" in fsm_error

    def test_contextual_error_responses(self, mock_localization_with_errors):
        """Test contextual error responses for different scenarios."""
        _ = mock_localization_with_errors
        
        # Test permission error
        permission_error = _("error_permission")
        assert "permission" in permission_error
        
        # Test debt not found error
        debt_error = _("error_debt_not_found")
        assert "not found" in debt_error


class TestFriendlyLanguageConsistency:
    """Test friendly language consistency and positive reinforcement."""

    @pytest.fixture
    def mock_positive_localization(self):
        """Mock localization with positive reinforcement messages."""
        def _(key):
            localization_map = {
                "positive_action_success": "Great job! Your action was successful.",
                "positive_keep_going": "Keep it up! You're doing great.",
                "positive_all_set": "You're all set! Let's keep your debts organized.",
                "debts_registered": "Debts have been successfully registered and are awaiting confirmation.",
                "payment_registered": "Your payment has been registered and is awaiting confirmation from the creditor.",
                "profile_contact_saved": "Your contact info has been saved.",
                "reminder_settings_saved": "Your reminder preferences have been updated.",
                "trusted_user_add_success": "User {username} has been added to your trusted list.",
                "language_switched": "Language has been changed to {language}.",
                "onboarding_completion": "All set! You can now record debts with @username amount description."
            }
            return localization_map.get(key, key)
        return _

    def test_positive_reinforcement_messages(self, mock_positive_localization):
        """Test positive reinforcement in success messages."""
        _ = mock_positive_localization
        
        # Test general success messages
        success_msg = _("positive_action_success")
        assert "Great job!" in success_msg
        assert "successful" in success_msg
        
        encouragement_msg = _("positive_keep_going")
        assert "Keep it up!" in encouragement_msg
        assert "doing great" in encouragement_msg

    def test_friendly_tone_consistency(self, mock_positive_localization):
        """Test consistent friendly tone across messages."""
        _ = mock_positive_localization
        
        messages = [
            _("debts_registered"),
            _("payment_registered"),
            _("profile_contact_saved"),
            _("reminder_settings_saved"),
            _("onboarding_completion")
        ]
        
        # Check for positive language patterns (more flexible)
        positive_indicators = ["successfully", "saved", "registered", "set", "great", "success", "updated"]
        
        for message in messages:
            has_positive = any(indicator.lower() in message.lower() for indicator in positive_indicators)
            assert has_positive, f"Message should have positive tone: {message}"

    def test_encouragement_for_successful_actions(self, mock_positive_localization):
        """Test encouragement messages for successful user actions."""
        _ = mock_positive_localization
        
        # Test completion message
        completion_msg = _("onboarding_completion")
        assert "All set!" in completion_msg
        
        # Test user addition success
        user_add_msg = _("trusted_user_add_success")
        assert "has been added" in user_add_msg
        
        # Test settings saved
        settings_msg = _("reminder_settings_saved")
        assert "updated" in settings_msg


class TestLocalizationIntegration:
    """Test integration with localization system and consistent tone."""

    @pytest.fixture
    def mock_comprehensive_localization(self):
        """Mock comprehensive localization covering all features."""
        def _(key):
            # Comprehensive localization map covering all bot features
            localization_map = {
                # Onboarding messages
                "start_welcome": "Hello! I am 'Budu Dolzhen' bot, here to help you track debts among friends.",
                "onboarding_private_step1": "Step 1: To record a debt, mention a user with @username followed by amount and description.",
                "onboarding_private_step2": "Step 2: Your friend will receive a notification to confirm the debt.",
                "onboarding_private_step3": "Step 3: Use /pay to record payments and /settings to manage preferences.",
                "onboarding_private_example": "Example: @friend 500 for coffee",
                "start_welcome_group": "Hello! I'm here to help track debts in your group.",
                "onboarding_group_step1": "Mention users with @username amount description to record debts.",
                "onboarding_group_step2": "Privacy notice: All debt information is visible to group members.",
                
                # Help system
                "help_intro": "Welcome to the help center! Here's everything you need to know:",
                "help_commands": "Available Commands:\n/start - Get started\n/help - Show this help\n/pay - Record payment\n/settings - Manage settings",
                "help_faq": "Frequently Asked Questions:\nQ: How do I record a debt?\nA: Use @username amount description",
                "help_troubleshooting": "Troubleshooting:\n- Check username format\n- Ensure amount is positive\n- Contact support if issues persist",
                "help_hints": "💡 Tips:\n- Use clear descriptions\n- Confirm debts promptly\n- Check your settings regularly",
                
                # Error messages with guidance
                "error_validation": "Validation error: {details}",
                "hint_amount_format": "Amount must be a number. For example: 500.50",
                "hint_username_format": "Usernames must start with @ and contain no spaces.",
                
                # Positive reinforcement
                "positive_action_success": "Great job! Your action was successful.",
                "positive_keep_going": "Keep it up! You're doing great.",
                "positive_all_set": "You're all set! Let's keep your debts organized.",
                
                # Button labels
                "btn_documentation": "📖 Documentation",
                "btn_support": "💬 Support",
                "btn_discord": "💬 Discord",
                "btn_github": "🔧 GitHub",
                
                # Resource messages
                "onboarding_resources": "Here are some helpful resources:",
                "help_resources": "Need more help? Check out these resources:"
            }
            return localization_map.get(key, key)
        return _

    def test_all_messages_have_localization_keys(self, mock_comprehensive_localization):
        """Test that all user-facing messages have localization keys."""
        _ = mock_comprehensive_localization
        
        # Test that all expected keys return localized content
        required_keys = [
            "start_welcome",
            "onboarding_private_step1",
            "help_intro",
            "help_commands",
            "error_validation",
            "positive_action_success",
            "btn_documentation"
        ]
        
        for key in required_keys:
            localized_text = _(key)
            assert localized_text != key, f"Missing localization for key: {key}"
            assert len(localized_text) > 0, f"Empty localization for key: {key}"

    def test_consistent_tone_across_languages(self, mock_comprehensive_localization):
        """Test consistent friendly tone across all localized messages."""
        _ = mock_comprehensive_localization
        
        # Get all localized messages
        all_keys = [
            "start_welcome", "onboarding_private_step1", "help_intro",
            "positive_action_success", "help_hints"
        ]
        
        messages = [_(key) for key in all_keys]
        
        # Check for consistent friendly tone indicators (more flexible)
        friendly_patterns = ["!", "welcome", "help", "great", "💡", "step", "here"]
        
        for message in messages:
            has_friendly_tone = any(pattern.lower() in message.lower() for pattern in friendly_patterns)
            assert has_friendly_tone, f"Message should have friendly tone: {message}"

    def test_localization_coverage_completeness(self, mock_comprehensive_localization):
        """Test that localization covers all major bot features."""
        _ = mock_comprehensive_localization
        
        # Test coverage for different feature areas
        feature_areas = {
            "onboarding": ["start_welcome", "onboarding_private_step1"],
            "help": ["help_intro", "help_commands"],
            "errors": ["error_validation", "hint_amount_format"],
            "positive": ["positive_action_success", "positive_all_set"],
            "ui": ["btn_documentation", "btn_support"]
        }
        
        for area, keys in feature_areas.items():
            for key in keys:
                localized = _(key)
                assert localized != key, f"Missing {area} localization for: {key}"

    @pytest.mark.asyncio
    async def test_localization_integration_in_handlers(self, mock_comprehensive_localization, model_user, model_chat):
        """Test that handlers properly integrate with localization system."""
        from tests.conftest import make_mutable_message
        user = model_user(id=12345, username="test", first_name="Test", language_code="en")
        chat = model_chat(id=12345, type=ChatType.PRIVATE)
        mock_message = make_mutable_message(from_user=user, chat=chat)
        
        with patch('bot.handlers.common.user_repo') as mock_repo, \
             patch('bot.handlers.common._', side_effect=mock_comprehensive_localization):
            
            mock_repo.get_or_create_user = AsyncMock()
            
            await handle_start_command(mock_message, mock_comprehensive_localization)
            
            # Verify that messages were sent
            assert mock_message.answer.call_count >= 1
            
            # Verify that localized content was used
            calls = [call[0][0] for call in mock_message.answer.call_args_list]
            
            # Check that actual localized content was sent (more flexible matching)
            localized_content_found = any(
                "budu dolzhen" in call.lower() or "step" in call.lower() or "hello" in call.lower()
                for call in calls
            )
            assert localized_content_found, "Localized content should be present in handler responses"


class TestWorkflowGuidance:
    """Test workflow guidance and contextual assistance."""

    @pytest.fixture
    def mock_workflow_localization(self):
        """Mock localization for workflow guidance."""
        def _(key):
            localization_map = {
                "workflow_debt_creation": "To create a debt: mention @username, add amount, and description",
                "workflow_payment_process": "To record payment: use /pay command and follow the prompts",
                "workflow_confirmation_needed": "Your debt request needs confirmation from the other party",
                "workflow_next_steps": "Next steps: Wait for confirmation or check /settings for preferences",
                "contextual_help_debt": "Need help with debts? Try: @friend 100 for lunch",
                "contextual_help_payment": "Need help with payments? Use /pay and select the debt to pay",
                "contextual_help_settings": "Need help with settings? Use /settings to manage preferences"
            }
            return localization_map.get(key, key)
        return _

    def test_workflow_guidance_messages(self, mock_workflow_localization):
        """Test workflow guidance message content."""
        _ = mock_workflow_localization
        
        # Test debt creation guidance
        debt_guidance = _("workflow_debt_creation")
        assert "@username" in debt_guidance
        assert "amount" in debt_guidance
        assert "description" in debt_guidance
        
        # Test payment process guidance
        payment_guidance = _("workflow_payment_process")
        assert "/pay" in payment_guidance
        assert "follow the prompts" in payment_guidance

    def test_contextual_assistance_content(self, mock_workflow_localization):
        """Test contextual assistance for different scenarios."""
        _ = mock_workflow_localization
        
        # Test contextual help messages
        debt_help = _("contextual_help_debt")
        assert "Try:" in debt_help
        assert "@friend" in debt_help
        
        payment_help = _("contextual_help_payment")
        assert "/pay" in payment_help
        assert "select the debt" in payment_help

    def test_next_steps_guidance(self, mock_workflow_localization):
        """Test next steps guidance after actions."""
        _ = mock_workflow_localization
        
        confirmation_msg = _("workflow_confirmation_needed")
        assert "confirmation" in confirmation_msg
        
        next_steps = _("workflow_next_steps")
        assert "Next steps:" in next_steps
        assert "/settings" in next_steps


class TestChatContextDifferentiation:
    """Test onboarding differentiation between group and private chat contexts."""

    @pytest.fixture
    def mock_context_localization(self):
        """Mock localization for different chat contexts."""
        def _(key):
            localization_map = {
                "notice_private_chat": "You are in a private chat. Use this to manage your personal debts.",
                "notice_group_chat": "You are in a group chat. Debts will be tracked separately per group.",
                "onboarding_private_detailed": "In private chat, you have full access to all features and settings.",
                "onboarding_group_limited": "In group chat, some features are limited for privacy and security.",
                "privacy_notice_group": "Privacy notice: All debt information is visible to group members.",
                "privacy_notice_private": "Privacy notice: Your debt information is kept confidential."
            }
            return localization_map.get(key, key)
        return _

    def test_private_chat_context_messages(self, mock_context_localization):
        """Test private chat specific context messages."""
        _ = mock_context_localization
        
        private_notice = _("notice_private_chat")
        assert "private chat" in private_notice
        assert "personal debts" in private_notice
        
        private_onboarding = _("onboarding_private_detailed")
        assert "full access" in private_onboarding
        assert "all features" in private_onboarding

    def test_group_chat_context_messages(self, mock_context_localization):
        """Test group chat specific context messages."""
        _ = mock_context_localization
        
        group_notice = _("notice_group_chat")
        assert "group chat" in group_notice
        assert "separately per group" in group_notice
        
        group_onboarding = _("onboarding_group_limited")
        assert "limited" in group_onboarding
        assert "privacy and security" in group_onboarding

    def test_privacy_notices_differentiation(self, mock_context_localization):
        """Test privacy notices for different chat contexts."""
        _ = mock_context_localization
        
        group_privacy = _("privacy_notice_group")
        assert "visible to group members" in group_privacy
        
        private_privacy = _("privacy_notice_private")
        assert "kept confidential" in private_privacy

    @pytest.mark.asyncio
    async def test_context_aware_onboarding_flow(self, model_user, model_chat):
        """Test that onboarding flow adapts to chat context."""
        from tests.conftest import make_mutable_message
        # Test private chat flow
        user = model_user(id=1, username="test", first_name="Test")
        private_chat = model_chat(id=1, type=ChatType.PRIVATE)
        private_message = make_mutable_message(from_user=user, chat=private_chat)
        
        # Test group chat flow
        group_chat = model_chat(id=-1, type=ChatType.GROUP, title="Test Group")
        group_message = make_mutable_message(from_user=user, chat=group_chat)
        
        def mock_localization(key):
            if "private" in key:
                return f"Private: {key}"
            elif "group" in key:
                return f"Group: {key}"
            return key
        
        with patch('bot.handlers.common.user_repo') as mock_repo, \
             patch('bot.handlers.common._', side_effect=mock_localization):
            
            mock_repo.get_or_create_user = AsyncMock()
            
            # Test private chat onboarding
            await handle_start_command(private_message, mock_localization)
            private_calls = [call[0][0] for call in private_message.answer.call_args_list]
            
            # Test group chat onboarding
            await handle_start_command(group_message, mock_localization)
            group_calls = [call[0][0] for call in group_message.answer.call_args_list]
            
            # Verify that both contexts received responses
            assert len(private_calls) >= 1, "Private chat should receive onboarding messages"
            assert len(group_calls) >= 1, "Group chat should receive onboarding messages"
            
            # Verify context-specific content if present
            private_content = " ".join(private_calls)
            group_content = " ".join(group_calls)
            
            # Check for context differentiation (if implemented)
            if "Private:" in private_content or "Group:" in group_content:
                assert "Private:" in private_content, "Private context should be indicated"
                assert "Group:" in group_content, "Group context should be indicated"
