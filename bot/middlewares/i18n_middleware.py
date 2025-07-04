import json
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, Optional

from aiogram import BaseMiddleware
from aiogram.types import Update

from ..db.models import User as UserModel

LOCALES_DIR = Path(__file__).parent.parent / "locales"


def get_i18n_instance(domain="bot"):
    """
    Creates a simple i18n factory using JSON files.
    This provides a gettext-like function for localization.
    """
    translations = {}
    for loc in LOCALES_DIR.glob("*.json"):
        lang = loc.stem
        with open(loc, "r", encoding="utf-8") as f:
            translations[lang] = json.load(f)

    def gettext_func(lang: str):
        # Fallback to a default language if a key is missing or lang is not supported
        lang_data = translations.get(lang, translations.get("ru", {}))
        
        def _(text_key: str, **kwargs) -> str:
            template = lang_data.get(text_key, text_key)
            try:
                return template.format(**kwargs)
            except KeyError:
                # In case of missing format keys, return the raw template
                return template

        return _

    return gettext_func


# A simple factory to get the translator function
i18n_factory = get_i18n_instance()


class I18nMiddleware(BaseMiddleware):
    """
    A simple JSON-based middleware for message localization.
    """
    async def __call__(
        self,
        handler: Callable[[Update, Dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: Dict[str, Any],
    ) -> Any:
        db_user: Optional[UserModel] = data.get("db_user")
        lang_code = db_user.language_code if db_user and db_user.language_code else "ru"
        
        # Provide the gettext-like function to handlers
        data["_"] = i18n_factory(lang_code)

        return await handler(event, data) 