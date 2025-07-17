import json
import logging
import time
import asyncio
from typing import Any, Awaitable, Callable, Dict, Optional, Set, Tuple

from aiogram import BaseMiddleware
from aiogram.types import Update, Message, CallbackQuery

from ..db.models import User as UserModel
from bot.locales import LOCALES_DIR
from ..handlers.language_handlers import (
    detect_user_language_from_telegram,
    get_user_language_preference,
)
from ..db.repositories import UserRepository

logger = logging.getLogger(__name__)

# Language preference cache: user_id -> (lang_code, timestamp)
_lang_cache: Dict[int, Tuple[str, float]] = {}
_cache_lock = asyncio.Lock()
CACHE_TTL = 300  # seconds


def get_i18n_instance(domain: str = "bot") -> Callable[[str], Callable[..., str]]:
    """
    Creates a simple i18n factory using JSON files.
    Provides a gettext-like function for localization with coverage validation.
    """
    translations: Dict[str, Dict[str, Any]] = {}
    for loc in LOCALES_DIR.glob("*.json"):
        lang = loc.stem
        try:
            with open(loc, "r", encoding="utf-8") as f:
                translations[lang] = json.load(f)
        except Exception as e:
            logger.error("Failed to load locale file %s: %s", loc, e)

    # Coverage validation: ensure all languages have the same keys
    all_keys: Set[str] = set()
    for lang_data in translations.values():
        all_keys.update(lang_data.keys())
    for lang, lang_data in translations.items():
        missing_keys = all_keys - set(lang_data.keys())
        if missing_keys:
            logger.warning("Missing translation keys for '%s': %s", lang, missing_keys)

    # Track runtime missing keys to avoid log spamming
    runtime_missing: Set[Tuple[str, str]] = set()

    def gettext_func(lang: str) -> Callable[..., str]:
        lang_data = translations.get(lang, translations.get("ru", {}))

        def _(text_key: str, **kwargs) -> str:
            template = lang_data.get(text_key)
            if template is None:
                if (lang, text_key) not in runtime_missing:
                    logger.debug(
                        "Missing translation for key '%s' in lang '%s'", text_key, lang
                    )
                    runtime_missing.add((lang, text_key))
                template = text_key
            try:
                return template.format(**kwargs)
            except KeyError as e:
                logger.error(
                    "Formatting error for key '%s' in lang '%s': missing param %s",
                    text_key,
                    lang,
                    e,
                )
                return template

        return _

    return gettext_func


i18n_factory = get_i18n_instance()


class I18nMiddleware(BaseMiddleware):
    """
    Middleware for dynamic language detection, caching, and localization.
    """

    async def __call__(
        self,
        handler: Callable[[Update, Dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: Dict[str, Any],
    ) -> Any:
        # allow instance-level patching by delegating to overridden callable if present
        override = self.__dict__.get("__call__")
        if override is not None and override is not I18nMiddleware.__call__:
            return await override(handler, event, data)
        # Extract user_id and Telegram language_code from the incoming update
        user_id: Optional[int] = None
        telegram_lang: Optional[str] = None

        if (
            hasattr(event, "message")
            and isinstance(event.message, Message)
            and event.message.from_user
        ):
            user_id = event.message.from_user.id
            telegram_lang = event.message.from_user.language_code
        elif (
            hasattr(event, "callback_query")
            and isinstance(event.callback_query, CallbackQuery)
            and event.callback_query.from_user
        ):
            user_id = event.callback_query.from_user.id
            telegram_lang = event.callback_query.from_user.language_code

        # Automatic language detection from Telegram settings
        if user_id and telegram_lang:
            try:
                new_lang = await detect_user_language_from_telegram(
                    user_id, telegram_lang, UserRepository
                )
                if new_lang:
                    async with _cache_lock:
                        _lang_cache[user_id] = (new_lang, time.time())
                    if data.get("db_user"):
                        data["db_user"].language_code = new_lang
            except Exception as e:
                logger.error("Error detecting language for user %d: %s", user_id, e)

        # Determine language preference (cache -> db_user -> DB fetch -> fallback)
        now = time.time()
        lang_code: str

        if user_id:
            async with _cache_lock:
                cache_entry = _lang_cache.get(user_id)
            if cache_entry and (now - cache_entry[1] < CACHE_TTL):
                lang_code = cache_entry[0]
            else:
                db_user: Optional[UserModel] = data.get("db_user")
                if db_user and db_user.language_code:
                    lang_code = db_user.language_code
                elif user_id:
                    try:
                        lang_code = await get_user_language_preference(user_id)
                    except Exception as e:
                        logger.error(
                            "Failed to get language preference for user %d: %s",
                            user_id,
                            e,
                        )
                        lang_code = "ru"
                else:
                    lang_code = "ru"
                async with _cache_lock:
                    _lang_cache[user_id] = (lang_code, now)
        else:
            lang_code = "ru"

        # Provide the gettext-like function and lang_code to handlers
        data["_"] = i18n_factory(lang_code)
        data["lang_code"] = lang_code

        return await handler(event, data)
