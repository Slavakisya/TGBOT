"""Fallback stubs for :mod:`python-telegram-bot` used in unit tests.

In production the real library should be used. When it is installed we load it
via :mod:`importlib` and simply re-export its contents.  The lightweight stub is
only retained for environments (CI, local unit tests) where the dependency is
intentionally absent.  Tests opt in to the stub via the
``HELPDESK_BOT_FORCE_STUB`` environment variable.
"""

from __future__ import annotations

from dataclasses import dataclass
import importlib.metadata
import importlib.util
import os
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, Sequence

__all__: list[str] = []
__helpdesk_bot_is_stub__ = True


def _load_real_package() -> ModuleType | None:
    """Try to load the real :mod:`telegram` package if it is installed."""

    if os.environ.get("HELPDESK_BOT_FORCE_STUB") == "1":
        return None

    try:
        dist = importlib.metadata.distribution("python-telegram-bot")
    except importlib.metadata.PackageNotFoundError:
        return None

    package_dir = Path(dist.locate_file("telegram"))
    init_py = package_dir / "__init__.py"
    if not init_py.exists():
        return None

    spec = importlib.util.spec_from_file_location(
        "telegram", init_py, submodule_search_locations=[str(package_dir)]
    )
    if spec is None or spec.loader is None:
        return None

    module = importlib.util.module_from_spec(spec)
    # Register the module so that intra-package imports work while executing it.
    sys.modules["telegram"] = module
    spec.loader.exec_module(module)
    return module


_real_module = _load_real_package()

if _real_module is not None:  # pragma: no cover - exercised when dependency is installed
    __helpdesk_bot_is_stub__ = False
    globals().update(vars(_real_module))
    __all__ = getattr(_real_module, "__all__", list(vars(_real_module)))
    sys.modules[__name__] = _real_module
else:

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
        """Very small container mimicking :class:`telegram.Update`."""

        def __init__(self, **kwargs: Any) -> None:
            for key, value in kwargs.items():
                setattr(self, key, value)


    __all__ = [
        "ReplyKeyboardMarkup",
        "InlineKeyboardButton",
        "InlineKeyboardMarkup",
        "Update",
    ]
