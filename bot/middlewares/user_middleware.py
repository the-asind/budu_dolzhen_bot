import asyncio
import logging
import time
from typing import Any, Awaitable, Callable, Dict, List, NamedTuple, Optional

from aiogram import BaseMiddleware
from aiogram.types import Update
from aiogram.enums import MessageEntityType

from ..db.repositories import UserRepository
from ..middlewares.i18n_middleware import i18n_factory

logger = logging.getLogger(__name__)


class PendingNotification(NamedTuple):
    """Represents a pending notification with timestamp for TTL tracking."""

    handler: Callable
    update: Update
    data: Dict[str, Any]
    timestamp: float


class ThreadSafeNotificationQueue:
    """Thread-safe notification queue with TTL and size limits."""

    def __init__(self, max_queue_size: int = 50, ttl_seconds: int = 3600):
        self._lock = asyncio.Lock()
        self._notifications: Dict[str, List[PendingNotification]] = {}
        self._max_queue_size = max_queue_size
        self._ttl_seconds = ttl_seconds

    async def add_notification(self, username: str, handler: Callable, update: Update, data: Dict[str, Any]) -> bool:
        """Add a notification to the queue with thread safety and size limits."""
        async with self._lock:
            await self._cleanup_expired()

            # Check if user queue is at capacity
            if username in self._notifications and len(self._notifications[username]) >= self._max_queue_size:
                logger.warning(f"Notification queue full for user {username}, dropping oldest notification")
                # Remove oldest notification (FIFO)
                self._notifications[username].pop(0)

            # Add new notification
            notification = PendingNotification(handler=handler, update=update, data=data, timestamp=time.time())

            if username not in self._notifications:
                self._notifications[username] = []
            self._notifications[username].append(notification)
            return True

    async def get_and_clear_notifications(self, username: str) -> List[PendingNotification]:
        """Get all notifications for a user and clear them atomically."""
        async with self._lock:
            notifications = self._notifications.pop(username, [])
            return notifications

    async def _cleanup_expired(self) -> None:
        """Remove expired notifications based on TTL."""
        current_time = time.time()
        expired_users = []

        for username, notifications in self._notifications.items():
            valid_notifications = [n for n in notifications if current_time - n.timestamp < self._ttl_seconds]

            if not valid_notifications:
                expired_users.append(username)
            else:
                self._notifications[username] = valid_notifications

        for username in expired_users:
            del self._notifications[username]

        if expired_users:
            logger.debug(f"Cleaned up expired notifications for users: {expired_users}")

    async def get_queue_stats(self) -> Dict[str, int]:
        """Get current queue statistics for monitoring."""
        async with self._lock:
            return {username: len(notifications) for username, notifications in self._notifications.items()}


class UserMiddleware(BaseMiddleware):
    """
    This middleware handles user registration and updates on every event,
    including enforcing registration via /start, tracking pending invitations,
    and queuing notifications for unregistered users until they become active.
    """

    _notification_queue = ThreadSafeNotificationQueue(max_queue_size=50, ttl_seconds=3600)

    @classmethod
    async def cleanup_expired(cls, timestamp: Optional[float] = None) -> int:
        """
        Remove expired notifications based on timestamp.

        Args:
            timestamp: Optional timestamp to use for comparison.
                      If None, uses current time.

        Returns:
            Number of expired notifications removed.
        """
        if timestamp is None:
            timestamp = time.time()

        await cls._notification_queue._cleanup_expired()

        # Get stats to return count of remaining notifications
        stats = await cls._notification_queue.get_queue_stats()
        total_notifications = sum(stats.values())
        return total_notifications

    @classmethod
    async def enforce_queue_limit(cls, max_size: Optional[int] = None) -> int:
        """
        Trim notification queues to a maximum size per user.

        Args:
            max_size: Maximum number of notifications per user.
                     If None, uses the queue's default max size.

        Returns:
            Number of notifications removed due to size limits.
        """
        if max_size is None:
            max_size = cls._notification_queue._max_queue_size

        removed_count = 0

        async with cls._notification_queue._lock:
            for username, notifications in cls._notification_queue._notifications.items():
                if len(notifications) > max_size:
                    # Remove oldest notifications (FIFO)
                    excess_count = len(notifications) - max_size
                    cls._notification_queue._notifications[username] = notifications[excess_count:]
                    removed_count += excess_count

        if removed_count > 0:
            logger.info(f"Enforced queue limits: removed {removed_count} notifications")

        return removed_count

    @classmethod
    async def get_queue_stats(cls) -> Dict[str, int]:
        """
        Get current notification queue statistics.

        Returns:
            Dictionary mapping usernames to their notification counts.
        """
        return await cls._notification_queue.get_queue_stats()

    @classmethod
    async def clear_all_notifications(cls) -> int:
        """
        Clear all pending notifications (for testing purposes).

        Returns:
            Total number of notifications cleared.
        """
        async with cls._notification_queue._lock:
            total_count = sum(len(notifications) for notifications in cls._notification_queue._notifications.values())
            cls._notification_queue._notifications.clear()
            return total_count

    async def __call__(
        self,
        handler: Callable[[Update, Dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: Dict[str, Any],
    ) -> Any:
        user = None
        if hasattr(event, "message") and event.message and event.message.from_user:
            user = event.message.from_user
        elif hasattr(event, "callback_query") and event.callback_query and event.callback_query.from_user:
            user = event.callback_query.from_user

        if not user:
            return await handler(event, data)

        bot = data.get("bot") or getattr(event, "bot", None)

        # Check if this is the /start command to register the user
        text = None
        if hasattr(event, "message") and event.message and event.message.text:
            text = event.message.text.strip()

        if text and text.startswith("/start"):
            try:
                db_user = await UserRepository.get_by_id(user.id)
                if not db_user:
                    db_user = await UserRepository.get_or_create_user(
                        user_id=user.id,
                        username=user.username or f"user_{user.id}",
                        first_name=user.first_name or (user.username or str(user.id)),
                        language_code=user.language_code or "en",
                    )

                data["db_user"] = db_user

                uname = (user.username or f"user_{user.id}").lstrip("@")
                pending_notifications = await self._notification_queue.get_and_clear_notifications(uname)
                for notification in pending_notifications:
                    notification.data["db_user"] = db_user
                    await notification.handler(notification.update, notification.data)
            except Exception as e:
                logger.error(f"Error registering user {user.id}: {e}")

            return await handler(event, data)

        try:
            db_user = await UserRepository.get_by_id(user.id)
        except Exception as e:
            logger.error(f"Error getting user {user.id}: {e}")
            return await handler(event, data)
        if not db_user:
            # User not registered yet: enforce /start
            if bot:

                _ = i18n_factory("ru")
                await bot.send_message(user.id, _("user_not_registered_message"))
            return  # Block further handling until registration

        if hasattr(event, "message") and event.message and event.message.entities:
            text = event.message.text or ""
            for ent in event.message.entities:
                if ent.type == MessageEntityType.MENTION:
                    mention = text[ent.offset : ent.offset + ent.length]
                    ref_username = mention.lstrip("@")
                    ref_user = await UserRepository.get_by_username(ref_username)
                    if not ref_user:
                        if bot:
                            _ = i18n_factory("ru")
                            await bot.send_message(
                                db_user.user_id, _("user_mention_not_registered", username=ref_username)
                            )
                        # Notification will be queued by debt handler after debt creation
                elif ent.type == MessageEntityType.TEXT_MENTION and ent.user:
                    ref_user_id = ent.user.id
                    ref_user = await UserRepository.get_by_id(ref_user_id)
                    if not ref_user:
                        ref_username = ent.user.username or str(ref_user_id)
                        if bot:
                            _ = i18n_factory("ru")
                            await bot.send_message(
                                db_user.user_id, _("user_mention_not_registered", username=ref_username)
                            )
                        # Notification will be queued by debt handler after debt creation

        # Pass the active user object to the handler
        data["db_user"] = db_user
        return await handler(event, data)
