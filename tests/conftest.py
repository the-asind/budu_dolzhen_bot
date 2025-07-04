"""
This file contains shared fixtures for the test suite.
"""

import os
import pytest
import sys
from unittest.mock import AsyncMock, MagicMock

# Set env vars before any application modules are imported
os.environ.setdefault("BOT_TOKEN", "test_token")
os.environ.setdefault("BOT_ADMIN_ID", "123")
os.environ.setdefault("DATABASE_PATH", ":memory:")


@pytest.fixture(scope="session", autouse=True)
def mock_bot_config_before_imports():
    """
    Forcefully mocks the bot's configuration module before any other imports.
    This is necessary to prevent Pydantic from loading the real settings during
    pytest's collection phase.
    """
    from bot.config import AppSettings, BotSettings, DatabaseSettings, SchedulerSettings

    # Create a mock settings object
    mock_settings = AppSettings(
        debug=True,
        log_level="DEBUG",
        bot=BotSettings(token="test_token", admin_id=123),
        db=DatabaseSettings(path=":memory:"),
        scheduler=SchedulerSettings(timezone="UTC")
    )

    # Create a mock config module
    mock_config_module = MagicMock()
    mock_config_module.get_settings.return_value = mock_settings
    
    # Forcefully insert the mock module into sys.modules
    sys.modules["bot.config"] = mock_config_module
    
    yield
    
    # Clean up by deleting the mock module from sys.modules
    del sys.modules["bot.config"]


@pytest.fixture
def mock_debt_repo() -> AsyncMock:
    """Returns an async mock for DebtRepository."""
    from bot.db.repositories import DebtRepository
    return AsyncMock(spec=DebtRepository) 