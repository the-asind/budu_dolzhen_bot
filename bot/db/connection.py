"""Async SQLite connection manager with pooling, migrations, and performance monitoring.

Wraps `aiosqlite` connections, initializes the database schema, handles migrations,
and provides a configurable connection pool for async database access.
"""

from __future__ import annotations

import os
import asyncio
import time
import logging
from pathlib import Path
from contextlib import asynccontextmanager
from typing import AsyncIterator

import aiosqlite

DATABASE_PATH = os.getenv("DATABASE_PATH", "bot.db")
POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "5"))
POOL_TIMEOUT = float(os.getenv("DB_POOL_TIMEOUT", "30"))  # seconds
CURRENT_SCHEMA_VERSION = 1


def find_project_root():
    current = Path(__file__).parent
    while current != current.parent:
        if (current / "pyproject.toml").exists():
            return current
        current = current.parent
    return Path(__file__).parents[2]  # fallback


SCHEMA_FILE = find_project_root() / "docs" / "schema.sql"
logger = logging.getLogger(__name__)

_pool: asyncio.Queue[aiosqlite.Connection] | None = None
_pool_lock = asyncio.Lock()
_pool_initialized = False


async def _initialize_schema(conn: aiosqlite.Connection) -> None:
    await conn.execute("PRAGMA foreign_keys = ON;")
    await conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT UNIQUE,
            first_name TEXT NOT NULL,
            last_name TEXT,
            language_code TEXT DEFAULT 'ru',
            contact TEXT,
            payday_days TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS trusted_users (
            user_id INTEGER NOT NULL,
            trusted_user_id INTEGER NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, trusted_user_id),
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
            FOREIGN KEY (trusted_user_id) REFERENCES users(user_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS debts (
            debt_id INTEGER PRIMARY KEY AUTOINCREMENT,
            creditor_id INTEGER NOT NULL,
            debtor_id INTEGER NOT NULL,
            amount INTEGER NOT NULL,
            description TEXT,
            status TEXT NOT NULL CHECK(status IN ('pending', 'active', 'paid', 'rejected')) DEFAULT 'pending',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            confirmed_at DATETIME,
            settled_at DATETIME,
            FOREIGN KEY (creditor_id) REFERENCES users(user_id) ON DELETE CASCADE,
            FOREIGN KEY (debtor_id) REFERENCES users(user_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS payments (
            payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            debt_id INTEGER NOT NULL,
            amount INTEGER NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('pending_confirmation', 'confirmed')) DEFAULT 'pending_confirmation',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            confirmed_at DATETIME,
            FOREIGN KEY (debt_id) REFERENCES debts(debt_id) ON DELETE CASCADE
        );
        """
    )
    await conn.commit()


async def _initialize_database() -> None:
    """Initialize database schema and run migrations if necessary."""
    try:
        async with aiosqlite.connect(DATABASE_PATH, timeout=POOL_TIMEOUT) as conn:
            await conn.execute("PRAGMA foreign_keys = ON;")
            cursor = await conn.execute("PRAGMA user_version;")
            row = await cursor.fetchone()
            current_version = row[0] if row else 0

            # If schema file exists, use it - otherwise, use built-in schema
            if current_version == 0:
                if SCHEMA_FILE.exists():
                    logger.info("Applying initial schema from %s", SCHEMA_FILE)
                    schema_sql = SCHEMA_FILE.read_text(encoding="utf-8")
                    await conn.executescript(schema_sql)
                    logger.info(
                        "Initial schema applied, version set to %d",
                        CURRENT_SCHEMA_VERSION,
                    )
                else:
                    logger.info(
                        "Applying built-in minimal schema (no schema.sql found)"
                    )
                    await _initialize_schema(conn)
                await conn.execute(f"PRAGMA user_version = {CURRENT_SCHEMA_VERSION};")
                await conn.commit()
            elif current_version < CURRENT_SCHEMA_VERSION:
                logger.info(
                    "Running migrations from version %d to %d",
                    current_version,
                    CURRENT_SCHEMA_VERSION,
                )
                await conn.execute(f"PRAGMA user_version = {CURRENT_SCHEMA_VERSION};")
                logger.info(
                    "Migrations applied, schema version updated to %d",
                    CURRENT_SCHEMA_VERSION,
                )
            else:
                logger.info(
                    "Database schema is up-to-date (version %d)", current_version
                )
    except Exception as e:
        logger.exception("Failed to initialize or migrate database: %s", e)
        raise


async def _initialize_pool() -> None:
    """Create and populate the connection pool."""
    global _pool, _pool_initialized

    # Special-case in-memory SQLite usage. `":memory:"` opens a new isolated
    # database per connection, so opening multiple connections would lead to
    # each one having its own empty schema. To make the database state
    # persistent across the pool we open **one** connection and reuse it for
    # every acquire. This approach is perfectly fine for unit-tests where the
    # workload is single-threaded and avoids having to switch to the (more
    # verbose) `file:memdb?mode=memory&cache=shared` URI in every test.
    if DATABASE_PATH == ":memory:":
        # Lazily create the schema on the very first (and only) connection
        conn = await aiosqlite.connect(
            DATABASE_PATH,
            timeout=POOL_TIMEOUT,
            cached_statements=128,
        )
        conn.row_factory = aiosqlite.Row
        await conn.execute("PRAGMA foreign_keys = ON;")
        # Ensure the schema exists on this shared connection.
        if SCHEMA_FILE.exists():
            schema_sql = SCHEMA_FILE.read_text(encoding="utf-8")
            await conn.executescript(schema_sql)
            # user_version pragma is part of schema.sql but ensure it's set
            await conn.execute(f"PRAGMA user_version = {CURRENT_SCHEMA_VERSION};")
        else:
            await _initialize_schema(conn)
        await conn.commit()

        _pool = asyncio.Queue(maxsize=10)
        for _ in range(10):
            await _pool.put(conn)
        _pool_initialized = True
        logger.info(
            "Database connection pool initialized with a shared in-memory connection (capacity: 10)"
        )
        return

    await _initialize_database()

    q: asyncio.Queue[aiosqlite.Connection] = asyncio.Queue(maxsize=POOL_SIZE)
    for i in range(POOL_SIZE):
        try:
            conn = await aiosqlite.connect(
                DATABASE_PATH,
                timeout=POOL_TIMEOUT,
                cached_statements=128,
            )
            conn.row_factory = aiosqlite.Row
            await conn.execute("PRAGMA foreign_keys = ON;")
            await conn.commit()
            await q.put(conn)
            logger.debug("Opened connection %d/%d", i + 1, POOL_SIZE)
        except Exception as e:
            logger.exception("Error opening database connection [%d]: %s", i + 1, e)
            raise
    _pool = q
    _pool_initialized = True
    logger.info("Database connection pool initialized with size %d", POOL_SIZE)


@asynccontextmanager
async def get_connection() -> AsyncIterator[aiosqlite.Connection]:
    """
    Acquire a database connection from the pool.

    Usage:
        async with get_connection() as conn:
            await conn.execute(...)
            await conn.commit()
    """
    global _pool, _pool_initialized

    if not _pool_initialized:
        async with _pool_lock:
            if not _pool_initialized:
                logger.info("Initializing database connection pool")
                await _initialize_pool()

    if _pool is None:
        raise RuntimeError("Connection pool is not initialized")
    try:
        conn = await asyncio.wait_for(_pool.get(), timeout=POOL_TIMEOUT)
        logger.debug("Acquired database connection from pool")
    except asyncio.TimeoutError:
        logger.error("Timed out waiting for database connection")
        raise RuntimeError("Database connection timeout")

    # Connection validation: recreate if invalid (especially for in-memory)
    try:
        await conn.execute("SELECT 1;")
    except Exception as e:
        logger.warning(
            "Database connection is invalid, recreating new connection: %s", e
        )
        try:
            new_conn = await aiosqlite.connect(
                DATABASE_PATH,
                timeout=POOL_TIMEOUT,
                cached_statements=128,
            )
            new_conn.row_factory = aiosqlite.Row
            await new_conn.execute("PRAGMA foreign_keys = ON;")
            await new_conn.commit()
            conn = new_conn
        except Exception as ex:
            logger.error("Failed to recreate database connection: %s", ex)

    start_time = time.monotonic()
    returned = False
    try:
        try:
            yield conn
        except GeneratorExit:
            # Ensure connection is returned to pool on generator exit
            try:
                await _pool.put(conn)
            except Exception:
                pass
            returned = True
            raise
        except Exception as e:
            logger.exception("Database operation error: %s", e)
            raise
    finally:
        elapsed = time.monotonic() - start_time
        logger.debug("Database connection held for %.3f seconds", elapsed)
        if not returned:
            try:
                await _pool.put(conn)
                logger.debug("Returned database connection to pool")
            except Exception as e:
                logger.error("Failed to return database connection to pool: %s", e)


async def close_pool() -> None:
    """Close all connections in the pool and reset its state."""
    global _pool, _pool_initialized

    if _pool is None:
        return

    while not _pool.empty():
        conn = await _pool.get()
        try:
            await conn.close()
        except Exception as exc:  # pragma: no cover - cleanup best effort
            logger.warning("Error closing DB connection: %s", exc)

    _pool = None
    _pool_initialized = False
    logger.info("Database connection pool closed")
