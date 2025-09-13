import sys
from pathlib import Path
import importlib
import pytest
import pytest_asyncio

# Add project module directory to sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent / 'helpdesk_bot'))

import db


@pytest_asyncio.fixture
async def temp_db(tmp_path, monkeypatch):
    monkeypatch.setenv('HELPDESK_DB_PATH', str(tmp_path / 'tickets.db'))
    importlib.reload(db)
    yield


@pytest.fixture
def bot(monkeypatch):
    monkeypatch.setenv('TELEGRAM_TOKEN', 'T')
    monkeypatch.setenv('ADMIN_IDS', '1')
    if 'bot' in sys.modules:
        del sys.modules['bot']
    return importlib.import_module('bot')
