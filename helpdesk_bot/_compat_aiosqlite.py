"""Fallback async sqlite helpers used when aiosqlite is unavailable."""

from __future__ import annotations

import asyncio
import sqlite3
from typing import Any, Iterable, Sequence


class Cursor:
    """Minimal async wrapper around ``sqlite3.Cursor``."""

    def __init__(self, cursor: sqlite3.Cursor):
        self._cursor = cursor

    @property
    def lastrowid(self) -> int:
        return self._cursor.lastrowid

    @property
    def rowcount(self) -> int:
        return self._cursor.rowcount

    async def fetchone(self):
        return await asyncio.to_thread(self._cursor.fetchone)

    async def fetchall(self):
        return await asyncio.to_thread(self._cursor.fetchall)


class Connection:
    """Async context manager exposing ``execute``/``commit`` methods."""

    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    async def execute(self, sql: str, params: Sequence[Any] | None = None) -> Cursor:
        if params is None:
            params = ()
        cursor = await asyncio.to_thread(self._conn.execute, sql, params)
        return Cursor(cursor)

    async def executemany(self, sql: str, seq_of_params: Iterable[Sequence[Any]]) -> None:
        await asyncio.to_thread(self._conn.executemany, sql, seq_of_params)

    async def commit(self) -> None:
        await asyncio.to_thread(self._conn.commit)

    async def close(self) -> None:
        await asyncio.to_thread(self._conn.close)


class _ConnectContext:
    def __init__(self, *args, **kwargs):
        self._args = args
        self._kwargs = kwargs
        self._conn: sqlite3.Connection | None = None

    async def __aenter__(self) -> Connection:
        args = list(self._args)
        kwargs = dict(self._kwargs)
        if args:
            args[0] = str(args[0])
        if "database" in kwargs:
            kwargs["database"] = str(kwargs["database"])
        kwargs.setdefault("check_same_thread", False)
        conn = await asyncio.to_thread(sqlite3.connect, *args, **kwargs)
        self._conn = conn
        return Connection(conn)

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._conn is not None:
            await asyncio.to_thread(self._conn.close)


def connect(*args, **kwargs) -> _ConnectContext:
    """Return an async context manager compatible with :func:`aiosqlite.connect`."""

    return _ConnectContext(*args, **kwargs)


__all__ = ["connect", "Connection", "Cursor"]
