import logging
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Update

logger = logging.getLogger(__name__)

class LoggingMiddleware(BaseMiddleware):
    """
    This middleware logs incoming updates.
    """
    async def __call__(
        self,
        handler: Callable[[Update, Dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: Dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        user_info = f"user={user.id}" if user else "user=unauthorized"

        logger.info(f"Update received: type={event.event_type}, {user_info}")
        
        try:
            return await handler(event, data)
        except Exception as e:
            logger.exception(f"Exception caught in handler for update {event.update_id}: {e}")
            raise 