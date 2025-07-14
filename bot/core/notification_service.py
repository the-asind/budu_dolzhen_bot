import logging
import asyncio

from typing import Optional, List, Dict, Any

from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup
from aiogram.exceptions import TelegramAPIError
from aiogram.exceptions import TelegramRetryAfter


from bot.db.models import Debt, User
from bot.keyboards.debt_kbs import (
    get_debt_confirmation_kb,
    get_payment_confirmation_kb
)

logger = logging.getLogger(__name__)


class NotificationService:
    """Service for sending and managing bot notifications."""

    def __init__(
        self,
        bot: Bot,
        rate_limit: int = 30,
        retry_attempts: int = 3
    ):
        self._bot = bot
        self._rate_limit = rate_limit
        self._retry_attempts = retry_attempts
        self._throttle_delay = 1.0 / rate_limit if rate_limit > 0 else 0
        self._unregistered_queue: Dict[int, List[Dict[str, Any]]] = {}

    async def send_message(
        self,
        chat_id: int,
        text: str,
        correlation_id: Optional[str] = None,
        **kwargs
    ) -> bool:
        """
        Sends a message with retry logic, rate limiting, and unregistered user handling.
        """
        for attempt in range(self._retry_attempts):
            try:
                await self._bot.send_message(chat_id, text, **kwargs)
                logger.debug(f"[{correlation_id}] Message sent to chat_id {chat_id}")
                return True
            except TelegramRetryAfter as e:
                logger.warning(f"[{correlation_id}] Rate limit hit, retrying after {e.retry_after}s")
                await asyncio.sleep(e.retry_after)
            except TelegramAPIError as e:
                err_text = str(e).lower()
                logger.warning(f"[{correlation_id}] Could not send message to {chat_id}: {e}")
                if self._is_unregistered_error(err_text):
                    # Queue message for later delivery
                    self._unregistered_queue.setdefault(chat_id, []).append({
                        "text": text,
                        "kwargs": kwargs,
                        "correlation_id": correlation_id
                    })
                    logger.debug(f"[{correlation_id}] Queued message for chat_id {chat_id} due to unregistered user")
                break
            finally:
                # Rate limiting throttle
                if self._throttle_delay:
                    await asyncio.sleep(self._throttle_delay)
        return False

    async def edit_message_text(
        self,
        chat_id: int,
        message_id: int,
        text: str,
        correlation_id: Optional[str] = None,
        **kwargs
    ) -> bool:
        """
        Edits an existing message with retry logic.
        """
        for attempt in range(self._retry_attempts):
            try:
                await self._bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=text,
                    **kwargs
                )
                logger.debug(f"[{correlation_id}] Message {message_id} in chat {chat_id} edited.")
                return True
            except TelegramRetryAfter as e:
                logger.warning(f"[{correlation_id}] Rate limit hit on edit, retrying after {e.retry_after}s")
                await asyncio.sleep(e.retry_after)
            except TelegramAPIError as e:
                logger.warning(f"[{correlation_id}] Could not edit message {message_id} in chat {chat_id}: {e}")
                break
            finally:
                if self._throttle_delay:
                    await asyncio.sleep(self._throttle_delay)
        return False

    async def send_debt_confirmation_request(
        self,
        debt: Debt,
        creditor: User,
        debtor: User,
        correlation_id: Optional[str] = None
    ) -> bool:
        """
        Sends a debt confirmation request to the debtor with inline Agree/Decline buttons.
        """
        lang = debtor.language_code or creditor.language_code
        keyboard = get_debt_confirmation_kb(debt.debt_id, lang)
        text = (
            f"👋 {debtor.username}, {creditor.username} says you owe them "
            f"{debt.amount / 100:.2f} for '{debt.description}'. Please confirm."
        )
        return await self.send_message(
            debtor.user_id,
            text,
            correlation_id=correlation_id,
            reply_markup=keyboard
        )

    async def send_payment_confirmation_request(
        self,
        payment_id: int,
        debt_id: int,
        amount: float,
        creditor: User,
        payer: User,
        correlation_id: Optional[str] = None
    ) -> bool:
        """
        Sends a payment confirmation request to the creditor with inline Approve/Reject buttons.
        """
        lang = creditor.language_code or payer.language_code
        keyboard = get_payment_confirmation_kb(payment_id, debt_id, lang)
        text = (
            f"💰 {creditor.username}, payment request #{payment_id} for debt "
            f"{debt_id} of ${amount:.2f} has been initiated by {payer.username}. "
            f"Please review."
        )        
        return await self.send_message(
            creditor.user_id,
            text,
            correlation_id=correlation_id,
            reply_markup=keyboard
        )

    async def animate_status_update(
        self,
        chat_id: int,
        message_id: int,
        texts: List[str],
        keyboards: Optional[List[InlineKeyboardMarkup]] = None,
        delay: float = 1.0,
        correlation_id: Optional[str] = None
    ) -> None:
        """
        Animates a sequence of status updates by editing the same message.
        """
        for idx, text in enumerate(texts):
            kwargs: Dict[str, Any] = {}
            if keyboards and idx < len(keyboards):
                kwargs["reply_markup"] = keyboards[idx]
            await self.edit_message_text(
                chat_id,
                message_id,
                text,
                correlation_id=correlation_id,
                **kwargs
            )
            await asyncio.sleep(delay)

    async def send_bulk_messages(
        self,
        chat_ids: List[int],
        text: str,
        correlation_id: Optional[str] = None,
        **kwargs
    ) -> Dict[int, bool]:
        """
        Sends the same message to multiple chat_ids with throttling.
        """
        results: Dict[int, bool] = {}
        for cid in chat_ids:
            ok = await self.send_message(cid, text, correlation_id=correlation_id, **kwargs)
            results[cid] = ok
        return results

    async def process_queued_notifications(
        self,
        correlation_id: Optional[str] = None
    ) -> None:
        """
        Attempts to resend messages queued for unregistered or unreachable users.
        """
        for chat_id, messages in list(self._unregistered_queue.items()):
            remaining: List[Dict[str, Any]] = []
            for msg in messages:
                ok = await self.send_message(
                    chat_id,
                    msg["text"],
                    correlation_id=msg.get("correlation_id") or correlation_id,
                    **msg.get("kwargs", {})
                )
                if not ok:
                    remaining.append(msg)
            if remaining:
                self._unregistered_queue[chat_id] = remaining
            else:
                del self._unregistered_queue[chat_id]

    def _is_unregistered_error(self, error_text: str) -> bool:
        """
        Determines if the error indicates an unregistered or blocked user.
        """
        return any(
            substr in error_text
            for substr in ("bot was blocked", "chat not found", "user is deactivated")
        )
