"""Package initialization for :mod:`helpdesk_bot`.

The project ships a lightweight stub of the :mod:`telegram` package that keeps
unit tests independent from the real ``python-telegram-bot`` dependency.  When
running inside those tests we default to the stub by setting the control
environment variable if it is not already provided and evicting any previously
imported real module.  Deployments that need the full dependency can opt in by
exporting ``HELPDESK_BOT_FORCE_STUB=0`` before importing the package.
"""

from __future__ import annotations

import os
import sys


if os.environ.setdefault("HELPDESK_BOT_FORCE_STUB", "1") == "1":
    sys.modules.pop("telegram", None)

