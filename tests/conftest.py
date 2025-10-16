import asyncio
import importlib
import inspect
import sys
from pathlib import Path

import pytest

try:  # pragma: no cover - exercised implicitly when dependency is installed
    import pytest_asyncio
except ModuleNotFoundError:  # pragma: no cover - fallback path
    pytest_asyncio = None

# Add project root to sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from helpdesk_bot import db


if pytest_asyncio is not None:

    @pytest_asyncio.fixture
    async def temp_db(tmp_path, monkeypatch):
        monkeypatch.setenv('HELPDESK_DB_PATH', str(tmp_path / 'tickets.db'))
        importlib.reload(db)
        yield

else:

    @pytest.fixture
    def temp_db(tmp_path, monkeypatch):
        monkeypatch.setenv('HELPDESK_DB_PATH', str(tmp_path / 'tickets.db'))
        module = sys.modules.get(db.__name__)
        if module is None:
            module = importlib.import_module(db.__name__)
        else:
            module = importlib.reload(module)
        globals()['db'] = module
        yield


    def pytest_pyfunc_call(pyfuncitem):
        """Execute async tests even when pytest-asyncio is unavailable."""

        if inspect.iscoroutinefunction(pyfuncitem.obj):
            kwargs = {
                name: pyfuncitem.funcargs[name]
                for name in pyfuncitem._fixtureinfo.argnames
            }
            asyncio.run(pyfuncitem.obj(**kwargs))
            return True


@pytest.fixture
def bot(monkeypatch):
    monkeypatch.setenv('TELEGRAM_TOKEN', 'T')
    monkeypatch.setenv('ADMIN_IDS', '1')
    if 'helpdesk_bot.bot' in sys.modules:
        del sys.modules['helpdesk_bot.bot']
    return importlib.import_module('helpdesk_bot.bot')
