"""Lightweight stubs for the :mod:`telegram` package used in tests.

These classes provide just enough behaviour for the bot code to import and run
in environments where python-telegram-bot is not installed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Sequence


@dataclass
class ReplyKeyboardMarkup:
    keyboard: Sequence[Sequence[str]]
    resize_keyboard: bool = False
    one_time_keyboard: bool = False


@dataclass
class InlineKeyboardButton:
    text: str
    callback_data: str | None = None


@dataclass
class InlineKeyboardMarkup:
    inline_keyboard: Sequence[Sequence[InlineKeyboardButton | str]]


class Update:
    """Very small container mimicking telegram.Update."""

    def __init__(self, **kwargs: Any) -> None:
        for key, value in kwargs.items():
            setattr(self, key, value)


__all__ = [
    "ReplyKeyboardMarkup",
    "InlineKeyboardButton",
    "InlineKeyboardMarkup",
    "Update",
]
