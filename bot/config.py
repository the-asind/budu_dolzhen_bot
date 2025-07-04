import logging
import os
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class BotSettings(BaseSettings):
    """Configuration for the Telegram bot."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", env_prefix="BOT_", extra="ignore"
    )

    token: str = Field(..., description="Telegram Bot Token from @BotFather")
    admin_id: int = Field(..., description="Admin's Telegram User ID for special commands")


class DatabaseSettings(BaseSettings):
    """Configuration for the database."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", env_prefix="DATABASE_", extra="ignore"
    )

    path: str = Field("budu_dolzhen.db", description="Path to the SQLite database file")


class SchedulerSettings(BaseSettings):
    """Configuration for the scheduler."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", env_prefix="SCHEDULER_", extra="ignore"
    )

    timezone: str = Field("UTC", description="Timezone for scheduler operations")


class AppSettings(BaseSettings):
    """General application settings."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    debug: bool = Field(False, description="Enable debug mode for development")
    log_level: str = Field("INFO", description="Logging level")

    bot: BotSettings = BotSettings()
    db: DatabaseSettings = DatabaseSettings()
    scheduler: SchedulerSettings = SchedulerSettings()

    @property
    def log_level_value(self) -> int:
        """Return the numeric value of the log level."""
        return logging.getLevelName(self.log_level.upper())


@lru_cache
def get_settings() -> AppSettings:
    """
    Get application settings.
    If the TEST_MODE environment variable is set, it returns a mock configuration
    suitable for testing, otherwise loads the configuration from the .env file.
    """
    if os.getenv("TEST_MODE"):
        return AppSettings(
            debug=True,
            log_level="DEBUG",
            bot=BotSettings(token="test_token", admin_id=123),
            db=DatabaseSettings(path=":memory:"),
            scheduler=SchedulerSettings(timezone="UTC")
        )
    return AppSettings() 