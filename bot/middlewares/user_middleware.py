from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import Update

from ..db.repositories import user_repo
from ..db.models import User as UserModel

class UserMiddleware(BaseMiddleware):
    """
    This middleware handles user registration and updates on every event.
    """
    async def __call__(
        self,
        handler: Callable[[Update, Dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: Dict[str, Any],
    ) -> Any:
        
        user = data.get("event_from_user")
        if not user:
            return await handler(event, data)

        db_user = await user_repo.get_or_create_user(
            user_id=user.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
            language_code=user.language_code,
        )

        # Pass the user object to the handler
        data["db_user"] = db_user
        
        return await handler(event, data) 