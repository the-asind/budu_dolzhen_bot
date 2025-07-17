import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from bot.config import get_settings
from bot.db.connection import get_connection
from bot.core.notification_service import NotificationService
from bot.middlewares.user_middleware import UserMiddleware
from bot.middlewares.i18n_middleware import I18nMiddleware
from bot.middlewares.logging_middleware import LoggingMiddleware
from bot.scheduler.scheduler_manager import scheduler_manager
from bot.handlers.common import router as common_router
from bot.handlers.debt_handlers import router as debt_router
from bot.handlers.payment_handlers import router as payment_router
from bot.handlers.profile_handlers import profile_router
from bot.handlers.inline_handlers import inline_router

async def main():
    """The main function that starts the bot."""
    settings = get_settings()

    logging.basicConfig(
        level=settings.log_level_value,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        stream=sys.stdout,
    )
    logger = logging.getLogger(__name__)

    async with get_connection():
        pass

    bot = Bot(
        token=settings.bot.token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    dp.update.outer_middleware(LoggingMiddleware())
    dp.update.outer_middleware(UserMiddleware())
    dp.update.outer_middleware(I18nMiddleware())

    notifier = NotificationService(bot)

    dp["notification_service"] = notifier

    dp.include_router(common_router)
    dp.include_router(debt_router)
    dp.include_router(payment_router)
    dp.include_router(profile_router)
    dp.include_router(inline_router)

    scheduler_manager.start()

    logger.info("Starting bot...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot stopped.")
    finally:
        scheduler_manager.shutdown()
        asyncio.run(db.disconnect()) 
