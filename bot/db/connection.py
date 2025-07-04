"""Minimal connection stub for repository layer during early TDD.

This stub avoids external dependencies while higher-level business logic is
developed. When real DB integration is introduced, this file will wrap
`aiosqlite` connections and migrations.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator, Any


@asynccontextmanager
async def get_connection() -> AsyncIterator[Any]:
    """Yield a dummy connection object (None)."""

    yield None 