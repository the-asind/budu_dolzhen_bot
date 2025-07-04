import logging
from typing import Optional

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError

from bot.db.models import Debt, User

logger = logging.getLogger(__name__)


class NotificationService:
    """Service for sending and managing bot notifications."""

    def __init__(self, bot: Bot):
        self._bot = bot

    async def send_message(
        self, chat_id: int, text: str, **kwargs
    ) -> bool:
        """
        Sends a message to a user.

        Args:
            chat_id: The user's Telegram ID.
            text: The message text to send.
            **kwargs: Additional parameters for aiogram's send_message.

        Returns:
            True if the message was sent successfully, False otherwise.
        """
        try:
            await self._bot.send_message(chat_id, text, **kwargs)
            logger.debug(f"Message sent to chat_id {chat_id}")
            return True
        except TelegramAPIError as e:
            # This can happen if the user blocked the bot, etc.
            logger.warning(f"Could not send message to chat_id {chat_id}: {e}")
            return False

    async def edit_message_text(
        self, chat_id: int, message_id: int, text: str, **kwargs
    ) -> bool:
        """
        Edits an existing message.

        Args:
            chat_id: The chat ID where the message is.
            message_id: The ID of the message to edit.
            text: The new text for the message.
            **kwargs: Additional parameters for aiogram's edit_message_text.

        Returns:
            True if the message was edited successfully, False otherwise.
        """
        try:
            await self._bot.edit_message_text(
                chat_id=chat_id, message_id=message_id, text=text, **kwargs
            )
            logger.debug(f"Message {message_id} in chat {chat_id} edited.")
            return True
        except TelegramAPIError as e:
            logger.warning(f"Could not edit message {message_id} in chat {chat_id}: {e}")
            return False

    async def send_debt_confirmation_request(self, debt: Debt, creditor: User, debtor: User):
        # In a real implementation, this would format a nice message
        # with inline buttons for confirmation.
        text = (
            f"Hi {debtor.username}, {creditor.username} says you owe them "
            f"{debt.amount / 100} for '{debt.description}'. Please confirm."
        )
        await self.send_message(debtor.id, text) 