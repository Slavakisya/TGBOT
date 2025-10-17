"""Minimal stub mimicking :mod:`aiosqlite` using the standard library.

This allows the bot and tests to run in environments where the optional
``aiosqlite`` dependency is not installed. Only the features used by the
project are implemented.
"""

from helpdesk_bot._compat_aiosqlite import connect, Connection, Cursor

__all__ = ["connect", "Connection", "Cursor"]
