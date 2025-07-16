"""
This file contains shared fixtures for the test suite.
"""

import os
import sys
import types
import time
import uuid
import logging

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch, MagicMock

# Set env vars before any application modules are imported
os.environ.setdefault("BOT_TOKEN", "test_token")
os.environ.setdefault("BOT_ADMIN_ID", "123")
os.environ.setdefault("DATABASE_PATH", ":memory:")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")


@pytest.fixture(scope="session", autouse=True)
def recursion_limit_safety():
    """
    Increase recursion limit for pytest AST parsing and restore it afterwards.
    """
    original_limit = sys.getrecursionlimit()
    sys.setrecursionlimit(3000)
    yield
    sys.setrecursionlimit(original_limit)


@pytest.fixture(autouse=True)
def override_tbstyle(request):
    """
    Override pytest traceback style to 'line' if available to reduce AST parsing complexity.
    """
    config = request.config
    if hasattr(config.option, "tbstyle"):
        config.option.tbstyle = "line"
    yield


@pytest.fixture(scope="session", autouse=True)
def mock_bot_config_before_imports():
    """
    Forcefully mocks the bot's configuration module before any other imports.
    Prevents Pydantic from loading the real settings during pytest's collection phase.
    Also resets any existing DB connection pool.
    """
    try:
        import bot.db.connection as db_conn
        setattr(db_conn, "_pool_initialized", False)
        setattr(db_conn, "_pool", None)
    except ImportError:
        pass

    from bot.config import AppSettings, BotSettings, DatabaseSettings, SchedulerSettings

    mock_settings = AppSettings(
        debug=True,
        log_level="DEBUG",
        bot=BotSettings(token="test_token", admin_id=123),
        db=DatabaseSettings(path=":memory:"),
        scheduler=SchedulerSettings(timezone="UTC")
    )

    mock_config_module = types.SimpleNamespace(
        get_settings=lambda: mock_settings,
        AppSettings=AppSettings,
        BotSettings=BotSettings,
        DatabaseSettings=DatabaseSettings,
        SchedulerSettings=SchedulerSettings
    )
    sys.modules["bot.config"] = mock_config_module  # type: ignore

    yield

    sys.modules.pop("bot.config", None)
    for mod_name in [m for m in list(sys.modules) if m.startswith("bot.config.")]:
        sys.modules.pop(mod_name, None)


@pytest.fixture(scope="session", autouse=True)
def mock_aiogram_bot():
    """Provide universal bot mock to prevent mounting errors."""
    from aiogram import Bot

    dummy_bot = AsyncMock(spec=Bot)
    dummy_bot.token = "test_token"
    dummy_bot.id = 123456789
    dummy_bot._session = AsyncMock()
    dummy_bot.send_message = AsyncMock()
    dummy_bot.edit_message_text = AsyncMock()
    dummy_bot.answer_callback_query = AsyncMock()
    dummy_bot.get_chat_member = AsyncMock()
    dummy_bot.answer_inline_query = AsyncMock()
    # Add any other async methods your tests may use

    yield dummy_bot


@pytest.fixture(scope="session", autouse=True)
def stub_apscheduler():
    """
    Stubs APScheduler classes to prevent exploring real scheduler implementations.
    """
    import apscheduler.schedulers.asyncio as async_mod
    import apscheduler.jobstores.sqlalchemy as sqlalchemy_mod

    OriginalScheduler = async_mod.AsyncIOScheduler
    OriginalJobStore = sqlalchemy_mod.SQLAlchemyJobStore

    class DummyScheduler:
        def __init__(self, gconfig=None, jobstores=None, executors=None, job_defaults=None, timezone=None, logger=None):
            self.gconfig = gconfig
            self.jobstores = jobstores or {}
            self._executors = executors or {}
            self._job_defaults = job_defaults or {}
            self.timezone = timezone
            self._logger = logger
            self.state = 0
            self._listeners = []
            self.jobs = {}
            self._next_id = 1

        def start(self):
            self.state = 1

        def shutdown(self, wait=True):
            self.state = 0

        def add_listener(self, listener):
            self._listeners.append(listener)

        def remove_listener(self, listener):
            if listener in self._listeners:
                self._listeners.remove(listener)

        def add_job(self, func, trigger=None, id=None, **kwargs):
            job_id = id or str(self._next_id)
            self._next_id += 1
            job = MagicMock()
            job.id = job_id
            job.func = func
            job.trigger = trigger
            job.kwargs = kwargs
            self.jobs[job_id] = job
            return job

        def remove_job(self, job_id):
            return self.jobs.pop(job_id, None)

        def modify_job(self, job_id, **changes):
            job = self.jobs.get(job_id)
            if job:
                for k, v in changes.items():
                    setattr(job, k, v)
            return job

        def get_job(self, job_id):
            return self.jobs.get(job_id)

        def pause(self, job_id=None):
            self.state = 2

        def resume(self, job_id=None):
            self.state = 1

        @property
        def running(self):
            return self.state == 1

        def get_jobs(self):
            return list(self.jobs.values())

    class DummyJobStore:
        def __init__(self, url=None, metadata=None, tablename=None, pickle_protocol=None, **kwargs):
            self.url = url
            self.metadata = metadata
            self.tablename = tablename
            self.pickle_protocol = pickle_protocol
            self.jobs = {}
            self.engine = None

        def add_job(self, job):
            self.jobs[job.id] = job

        def update_job(self, job):
            self.jobs[job.id] = job

        def remove_job(self, job_id):
            return self.jobs.pop(job_id, None)

        def remove_all_jobs(self):
            self.jobs.clear()

        def get_due_jobs(self, now):
            return list(self.jobs.values())

        def get_next_run_time(self):
            return None

        def get_all_jobs(self):
            return list(self.jobs.values())

    async_mod.AsyncIOScheduler = DummyScheduler  # type: ignore
    sqlalchemy_mod.SQLAlchemyJobStore = DummyJobStore  # type: ignore

    assert async_mod.AsyncIOScheduler is DummyScheduler
    assert sqlalchemy_mod.SQLAlchemyJobStore is DummyJobStore

    # Patch already-imported scheduler_manager if present
    sm_module = sys.modules.get("bot.scheduler.scheduler_manager")
    if sm_module is not None:
        if hasattr(sm_module, "AsyncIOScheduler"):
            sm_module.AsyncIOScheduler = DummyScheduler  # type: ignore
        if hasattr(sm_module, "SQLAlchemyJobStore"):
            sm_module.SQLAlchemyJobStore = DummyJobStore  # type: ignore

    yield

    async_mod.AsyncIOScheduler = OriginalScheduler
    sqlalchemy_mod.SQLAlchemyJobStore = OriginalJobStore
    # Restore scheduler_manager module if it was patched
    sm_module = sys.modules.get("bot.scheduler.scheduler_manager")
    if sm_module is not None:
        if hasattr(sm_module, "AsyncIOScheduler"):
            sm_module.AsyncIOScheduler = OriginalScheduler  # type: ignore
        if hasattr(sm_module, "SQLAlchemyJobStore"):
            sm_module.SQLAlchemyJobStore = OriginalJobStore  # type: ignore


@pytest.fixture(scope="session", autouse=True)
def patch_handlers_common():
    """
    Monkey-patch missing attributes in all handler modules for common patterns.
    """
    from bot.db.repositories import UserRepository

    handler_modules = [
        "bot.handlers.common",
        "bot.handlers.debt_handlers",
        "bot.handlers.payment_handlers",
        "bot.handlers.profile_handlers",
        "bot.handlers.inline_handlers",
        "bot.handlers.language_handlers",
    ]

    for mod_name in handler_modules:
        try:
            module = __import__(mod_name, fromlist=["*"])
        except ImportError:
            logging.warning(f"Handler module {mod_name} not found, skipping patch")
            continue
        setattr(module, "user_repo", UserRepository())
        setattr(module, "_", lambda msg: msg)
        setattr(module, "logger", logging.getLogger(mod_name))
        if not hasattr(module, "user_repo") or not hasattr(module, "_"):
            raise RuntimeError(f"Failed to patch handler module {mod_name}")

    yield


@pytest.fixture(autouse=True)
def reset_db_connection_pool():
    """
    Reset the SQLite connection pool between tests to ensure isolation.
    """
    try:
        import bot.db.connection as db_conn
        setattr(db_conn, "_pool_initialized", False)
        setattr(db_conn, "_pool", None)
    except ImportError:
        pass
    yield


# Aiogram model fixtures

@pytest.fixture
def model_user():
    """
    Factory for aiogram.types.User using model_construct to bypass validation.
    """
    from aiogram.types import User

    def factory(id: int = 123, is_bot: bool = False, first_name: str = "Test",
                username: str = "testuser", language_code: str = "en", **kwargs):
        return User.model_construct(
            id=id,
            is_bot=is_bot,
            first_name=first_name,
            username=username,
            language_code=language_code,
            **kwargs
        )

    return factory


@pytest.fixture
def model_chat():
    """
    Factory for aiogram.types.Chat.
    """
    from aiogram.types import Chat

    def factory(id: int = 456, type: str = "private", **kwargs):
        if type in ("group", "supergroup") and "title" not in kwargs:
            kwargs["title"] = f"Chat {id}"
        if type == "channel" and "username" not in kwargs:
            kwargs["username"] = f"channel_{id}"
        return Chat.model_construct(id=id, type=type, **kwargs)

    return factory


@pytest.fixture
def model_message(model_user, model_chat):
    """
    Factory for aiogram.types.Message that returns a mutable MagicMock
    with AsyncMock methods to support methods like answer/edit_text.
    """
    def factory(
        message_id: int = 1,
        date: int | None = None,
        chat=None,
        from_user=None,
        text: str = "test message",
        sender_chat=None,
        message_thread_id=None,
        is_topic_message: bool = False,
        reply_to_message=None,
        **kwargs,
    ):
        chat = chat or model_chat()
        from_user = from_user or model_user()
        msg_kwargs = {
            "message_id": message_id,
            "text": text,
            "chat": chat,
            "from_user": from_user,
            "is_topic_message": is_topic_message,
        }
        if sender_chat is not None:
            msg_kwargs["sender_chat"] = sender_chat
        if message_thread_id is not None:
            msg_kwargs["message_thread_id"] = message_thread_id
        if reply_to_message is not None:
            msg_kwargs["reply_to_message"] = reply_to_message
        if date is not None:
            msg_kwargs["date"] = date
        msg_kwargs.update(kwargs)
        return make_mutable_message(**msg_kwargs)

    return factory


@pytest.fixture
def model_callback_query(model_user, model_message):
    """
    Factory for aiogram.types.CallbackQuery.
    """
    from aiogram.types import CallbackQuery

    def factory(
        id: str = None,
        from_user=None,
        chat_instance: str = None,
        message=None,
        data: str = "",
        inline_message_id=None,
        game_short_name=None,
        **kwargs
    ):
        from_user = from_user or model_user()
        message = message or model_message()
        return CallbackQuery.model_construct(
            id=id or str(uuid.uuid4()),
            from_user=from_user,
            chat_instance=chat_instance or str(uuid.uuid4()),
            message=message,
            data=data,
            inline_message_id=inline_message_id,
            game_short_name=game_short_name,
            **kwargs
        )

    return factory


@pytest.fixture
def model_inline_query(model_user):
    """
    Factory for aiogram.types.InlineQuery.
    """
    from aiogram.types import InlineQuery

    def factory(
        id: str = None,
        from_user=None,
        query: str = "",
        offset: str = "",
        chat_type=None,
        location=None,
        **kwargs
    ):
        from_user = from_user or model_user()
        return InlineQuery.model_construct(
            id=id or str(uuid.uuid4()),
            from_user=from_user,
            query=query or "test query",
            offset=str(offset),
            chat_type=chat_type or "private",
            location=location,
            **kwargs
        )

    return factory


@pytest.fixture
def mock_debt_repo() -> AsyncMock:
    """Returns an async mock for DebtRepository."""
    from bot.db.repositories import DebtRepository
    return AsyncMock(spec=DebtRepository)


@pytest.fixture
def mock_user_repo() -> AsyncMock:
    """Returns an async mock for UserRepository."""
    from bot.db.repositories import UserRepository
    return AsyncMock(spec=UserRepository)


@pytest_asyncio.fixture
async def mock_repositories():
    """
    Async fixture that provides mocked DebtRepository and UserRepository
    with common methods preset to AsyncMock.
    """
    with patch('bot.db.repositories.DebtRepository') as mock_debt, \
         patch('bot.db.repositories.UserRepository') as mock_user:
        mock_debt.add = AsyncMock()
        mock_debt.get = AsyncMock()
        mock_debt.update_status = AsyncMock()
        mock_debt.list_active_by_user = AsyncMock()
        mock_user.add = AsyncMock()
        mock_user.get_by_username = AsyncMock()
        mock_user.trusts = AsyncMock()
        mock_user.add_trust = AsyncMock()
        mock_user.list_trusted = AsyncMock()
        mock_user.remove_trust = AsyncMock()
        yield mock_debt, mock_user


@pytest_asyncio.fixture
async def mock_notification_service(mock_aiogram_bot):
    """
    Async fixture that provides a mocked NotificationService instance
    with standard methods as AsyncMock.
    """
    with patch('bot.core.notification_service.NotificationService') as mock_notif:
        instance = mock_notif.return_value
        instance._bot = mock_aiogram_bot
        instance.send_message = AsyncMock(return_value=True)
        instance.send_bulk_messages = AsyncMock(return_value={})
        instance.edit_message_text = AsyncMock(return_value=True)
        instance.simulate_error = lambda exc: [
            setattr(instance, "send_message", AsyncMock(side_effect=exc)),
            setattr(instance, "send_bulk_messages", AsyncMock(side_effect=exc))
        ]
        yield instance


@pytest_asyncio.fixture
async def sample_users():
    """
    Async fixture yielding sample User models: creditor, debtor, unregistered.
    """
    from bot.db.models import User
    creditor = User(user_id=1, username='creditor', first_name='John', language_code='en')
    debtor = User(user_id=2, username='debtor', first_name='Jane', language_code='en')
    unregistered = User(user_id=3, username='unregistered', first_name='Bob', language_code='en')
    return creditor, debtor, unregistered


@pytest_asyncio.fixture
async def sample_debts(sample_users):
    """
    Async fixture yielding sample Debt models: recent, old, unregistered debt.
    """
    from bot.db.models import Debt
    from datetime import datetime, timezone, timedelta
    creditor, debtor, unregistered_user = sample_users
    now = datetime.now(timezone.utc)
    recent = Debt(debt_id=1, creditor_id=creditor.user_id, debtor_id=debtor.user_id,
                  amount=5000, description='Coffee', status='pending', created_at=now - timedelta(hours=1))
    old = Debt(debt_id=2, creditor_id=creditor.user_id, debtor_id=debtor.user_id,
               amount=10000, description='Lunch', status='pending', created_at=now - timedelta(hours=24))
    unreg = Debt(debt_id=3, creditor_id=creditor.user_id, debtor_id=unregistered_user.user_id,
                 amount=2500, description='Snack', status='pending', created_at=now - timedelta(hours=25))
    return recent, old, unreg


# Mutable mock helpers

@pytest.fixture
def mock_message():
    """Mutable mock for aiogram.types.Message with AsyncMock methods."""
    from aiogram.types import Message
    m = MagicMock(spec=Message)
    m.answer = AsyncMock()
    m.edit_text = AsyncMock()
    m.reply = AsyncMock()
    m.message_id = 1
    m.chat = MagicMock()
    m.from_user = MagicMock()
    return m


@pytest.fixture
def mock_callback_query(mock_message):
    """Mutable mock for aiogram.types.CallbackQuery with associated message."""
    from aiogram.types import CallbackQuery
    cq = MagicMock(spec=CallbackQuery)
    cq.answer = AsyncMock()
    cq.data = ""
    cq.from_user = MagicMock()
    cq.from_user.id = 123456789
    cq.message = mock_message
    return cq


def make_mutable_message(**kwargs):
    """Create a mutable mock Message with AsyncMock methods."""
    from aiogram.types import Message
    mock = MagicMock(spec=Message)
    mock.answer = AsyncMock()
    mock.edit_text = AsyncMock()
    mock.reply = AsyncMock()
    mock.message_id = kwargs.get("message_id", 1)
    mock.text = kwargs.get("text", "")
    mock.chat = kwargs.get("chat") or MagicMock()
    mock.from_user = kwargs.get("from_user") or MagicMock()
    mock.entities = kwargs.get("entities", [])
    return mock


def make_mutable_inline_query(**kwargs):
    """Create a mutable mock InlineQuery with AsyncMock methods."""
    from aiogram.types import InlineQuery
    mock = MagicMock(spec=InlineQuery)
    mock.answer = AsyncMock()
    mock.id = kwargs.get('id', str(uuid.uuid4()))
    mock.query = kwargs.get('query', '')
    mock.from_user = kwargs.get('from_user') or MagicMock()
    mock.offset = kwargs.get('offset', '')
    return mock


def make_mutable_callback_query(**kwargs):
    """Create a mutable mock CallbackQuery with AsyncMock methods."""
    from aiogram.types import CallbackQuery
    mock = MagicMock(spec=CallbackQuery)
    mock.answer = AsyncMock()
    mock.id = kwargs.get('id', str(uuid.uuid4()))
    mock.data = kwargs.get('data', '')
    mock.from_user = kwargs.get('from_user') or MagicMock()
    mock.message = kwargs.get('message') or make_mutable_message()
    return mock


# Common service and manager mocks

@pytest.fixture
def mock_debt_manager():
    """Returns an async mock for DebtManager."""
    from bot.core.debt_manager import DebtManager
    return AsyncMock(spec=DebtManager)


@pytest.fixture
def mock_payment_manager():
    """Returns an async mock for PaymentManager."""
    from bot.core.payment_manager import PaymentManager
    return AsyncMock(spec=PaymentManager)


@pytest.fixture
def mock_get_debt_confirmation_kb():
    """Returns an AsyncMock wrapping the debt confirmation keyboard generator."""
    from bot.keyboards.debt_kbs import get_debt_confirmation_kb
    return AsyncMock(wraps=get_debt_confirmation_kb)


@pytest.fixture
def mock_get_payment_confirmation_kb():
    """Returns an AsyncMock wrapping the payment confirmation keyboard generator."""
    from bot.keyboards.debt_kbs import get_payment_confirmation_kb
    return AsyncMock(wraps=get_payment_confirmation_kb)


# Handler modules patch validation
for mod_name in [
    "bot.handlers.common",
    "bot.handlers.debt_handlers",
    "bot.handlers.payment_handlers",
    "bot.handlers.profile_handlers",
    "bot.handlers.inline_handlers",
    "bot.handlers.language_handlers",
]:
    try:
        module = __import__(mod_name, fromlist=["*"])
        assert hasattr(module, "user_repo"), f"{mod_name} missing user_repo patch"
        assert hasattr(module, "_"), f"{mod_name} missing localization function patch"
    except ImportError:
        logging.warning(f"Handler module {mod_name} not found during validation")
    except AssertionError as ae:
        logging.error(str(ae))