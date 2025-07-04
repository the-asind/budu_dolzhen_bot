from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from typing import Callable

from ..db.repositories import user_repo

router = Router()


@router.message(Command(commands=["start"]))
async def handle_start_command(message: Message, _: Callable):
    """
    Handler for the /start command.
    Greets the user and registers them in the system.
    """
    user = message.from_user
    if not user:
        return

    await user_repo.get_or_create_user(
        user_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
        language_code=user.language_code,
    )
    
    await message.answer(_("start_welcome"))


@router.message(Command(commands=["help"]))
async def handle_help_command(message: Message, _: Callable):
    """
    Handler for the /help command.
    Provides a detailed help message with bot usage instructions.
    """
    await message.answer(_("help_message")) 