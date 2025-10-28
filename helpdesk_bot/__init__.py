"""Package initialization for :mod:`helpdesk_bot`.

The project ships a lightweight stub of the :mod:`telegram` package that keeps
unit tests independent from the real ``python-telegram-bot`` dependency.  When
running inside those tests we default to the stub by setting the control
environment variable if it is not already provided and evicting any previously
imported real module.  Deployments that need the full dependency can opt in by
exporting ``HELPDESK_BOT_FORCE_STUB=0`` before importing the package.
"""

from __future__ import annotations

import importlib
import os
import sys
from types import ModuleType
from typing import Final


def _ensure_telegram_stub() -> None:
    """Force the lightweight telegram stub unless explicitly disabled."""

    if os.environ.setdefault("HELPDESK_BOT_FORCE_STUB", "1") == "1":
        # Remove a previously imported real telegram package so that subsequent
        # imports resolve to the repository stub regardless of the environment
        # pythonpath order.
        sys.modules.pop("telegram", None)


_ensure_telegram_stub()


def _import(name: str) -> ModuleType:
    """Import a submodule relative to :mod:`helpdesk_bot`."""

    return importlib.import_module(f"{__name__}.{name}")


db: Final[ModuleType] = _import("db")

__all__ = ["db"]

