import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location("config_real", Path("bot/config.py"))
config_real = importlib.util.module_from_spec(spec)
spec.loader.exec_module(config_real)


def test_get_settings_without_admin(monkeypatch):
    monkeypatch.delenv("BOT_ADMIN_ID", raising=False)
    monkeypatch.setenv("BOT_TOKEN", "token")
    settings = config_real.get_settings()
    assert settings.bot.admin_id is None
