import types
import importlib
import sys
from datetime import timezone, timedelta
from pathlib import Path
import logging

import pytest


@pytest.fixture
def utils(monkeypatch):
    monkeypatch.setenv('TELEGRAM_TOKEN', 'T')
    monkeypatch.setenv('ADMIN_IDS', '1')
    if 'helpdesk_bot.utils' in sys.modules:
        del sys.modules['helpdesk_bot.utils']
    return importlib.import_module('helpdesk_bot.utils')


@pytest.fixture
def tickets(utils):
    if 'helpdesk_bot.handlers.tickets' in sys.modules:
        del sys.modules['helpdesk_bot.handlers.tickets']
    return importlib.import_module('helpdesk_bot.handlers.tickets')


def test_help_text_files_missing(monkeypatch, caplog):
    monkeypatch.setenv('TELEGRAM_TOKEN', 'T')
    monkeypatch.setenv('ADMIN_IDS', '1')

    original_read = Path.read_text

    def fake_read(self, *args, **kwargs):
        if self.name in {'rules.txt', 'links.txt'}:
            raise FileNotFoundError
        return original_read(self, *args, **kwargs)

    monkeypatch.setattr(Path, 'read_text', fake_read)
    if 'helpdesk_bot.utils' in sys.modules:
        del sys.modules['helpdesk_bot.utils']
    with caplog.at_level(logging.WARNING, logger='helpdesk_bot'):
        utils = importlib.import_module('helpdesk_bot.utils')

    assert utils.HELP_TEXT_RULES == 'Файл rules.txt не найден.'
    assert utils.HELP_TEXT_LINKS == 'Файл links.txt не найден.'
    assert 'rules.txt not found' in caplog.text
    assert 'links.txt not found' in caplog.text


def test_format_kyiv_time(utils, monkeypatch):
    captured = {}

    def fake_zoneinfo(name):
        captured['name'] = name
        return timezone(timedelta(hours=2))

    monkeypatch.setattr(utils, 'ZoneInfo', fake_zoneinfo)
    ts = '2023-03-01 10:00:00'
    assert utils.format_kyiv_time(ts) == '2023-03-01 12:00:00'
    assert captured['name'] == 'Europe/Kyiv'
    assert utils.format_kyiv_time('invalid') == 'invalid'


@pytest.mark.asyncio
async def test_row_handler_valid(tickets, utils):
    class DummyMessage:
        def __init__(self, text):
            self.text = text
            self.replies = []

        async def reply_text(self, text, reply_markup=None):
            self.replies.append(text)

    class DummyUpdate:
        def __init__(self, text):
            self.message = DummyMessage(text)

    ctx = types.SimpleNamespace(user_data={})
    update = DummyUpdate('3')
    state = await tickets.row_handler(update, ctx)
    assert state == utils.STATE_COMP
    assert ctx.user_data['row'] == '3'
    assert 'Введите номер компьютера' in update.message.replies[0]


@pytest.mark.asyncio
async def test_comp_handler_valid(tickets, utils):
    class DummyMessage:
        def __init__(self, text):
            self.text = text
            self.replies = []

        async def reply_text(self, text, reply_markup=None):
            self.replies.append(text)

    class DummyUpdate:
        def __init__(self, text):
            self.message = DummyMessage(text)

    ctx = types.SimpleNamespace(user_data={'row': '3'})
    update = DummyUpdate('5')
    state = await tickets.comp_handler(update, ctx)
    assert state == utils.STATE_PROBLEM_MENU
    assert ctx.user_data['row_comp'] == '3/5'
    assert 'Выберите тип проблемы' in update.message.replies[0]


@pytest.mark.asyncio
async def test_row_handler_cancel(bot):
    class DummyMessage:
        def __init__(self, text):
            self.text = text
            self.replies = []

        async def reply_text(self, text, reply_markup=None):
            self.replies.append(text)

    class DummyUpdate:
        def __init__(self, text):
            self.message = DummyMessage(text)

    ctx = types.SimpleNamespace(user_data={})
    update = DummyUpdate('Отмена')
    state = await bot.row_handler(update, ctx)
    assert state == bot.ConversationHandler.END
    assert 'Отменено' in update.message.replies[0]


@pytest.mark.asyncio
async def test_problem_menu_handler_valid(bot):
    class DummyMessage:
        def __init__(self, text):
            self.text = text
            self.replies = []

        async def reply_text(self, text, reply_markup=None):
            self.replies.append(text)

    class DummyUpdate:
        def __init__(self, text):
            self.message = DummyMessage(text)

    ctx = types.SimpleNamespace(user_data={})
    update = DummyUpdate(bot.PROBLEMS[1])
    state = await bot.problem_menu_handler(update, ctx)
    assert state == bot.STATE_CUSTOM_DESC
    assert ctx.user_data['problem'] == bot.PROBLEMS[1]
    assert 'Опишите свою проблему' in update.message.replies[0]


@pytest.mark.asyncio
async def test_problem_menu_handler_invalid(bot):
    class DummyMessage:
        def __init__(self, text):
            self.text = text
            self.replies = []

        async def reply_text(self, text, reply_markup=None):
            self.replies.append(text)

    class DummyUpdate:
        def __init__(self, text):
            self.message = DummyMessage(text)

    ctx = types.SimpleNamespace(user_data={})
    update = DummyUpdate('Неизвестная проблема')
    state = await bot.problem_menu_handler(update, ctx)
    assert state == bot.STATE_PROBLEM_MENU
    assert 'Выберите проблему из списка' in update.message.replies[0]


@pytest.mark.asyncio
async def test_problem_menu_handler_cancel(bot):
    class DummyMessage:
        def __init__(self, text):
            self.text = text
            self.replies = []

        async def reply_text(self, text, reply_markup=None):
            self.replies.append(text)

    class DummyUpdate:
        def __init__(self, text):
            self.message = DummyMessage(text)

    ctx = types.SimpleNamespace(user_data={})
    update = DummyUpdate('Отмена')
    state = await bot.problem_menu_handler(update, ctx)
    assert state == bot.ConversationHandler.END
    assert 'Отменено' in update.message.replies[0]


@pytest.mark.asyncio
async def test_custom_desc_handler_valid(bot, monkeypatch):
    class DummyMessage:
        def __init__(self, text):
            self.text = text
            self.replies = []

        async def reply_text(self, text, reply_markup=None):
            self.replies.append(text)

    class DummyUser:
        def __init__(self, user_id, name):
            self.id = user_id
            self.full_name = name

    class DummyUpdate:
        def __init__(self, text):
            self.message = DummyMessage(text)
            self.effective_user = DummyUser(42, 'User')

    class DummyBot:
        def __init__(self):
            self.sent = []

        async def send_message(self, chat_id, text, reply_markup=None):
            self.sent.append((chat_id, text))

    called = {}

    async def fake_add_ticket(rowc, prob, desc, fullname, uid):
        called['args'] = (rowc, prob, desc, fullname, uid)
        return 99

    async def fake_get_ticket(req_id):
        return [0, '', '', '', '', 42, '', '2023-03-01 10:00:00']

    monkeypatch.setattr(bot.db, 'add_ticket', fake_add_ticket)
    monkeypatch.setattr(bot.db, 'get_ticket', fake_get_ticket)

    rowc = '3/5'
    prob = bot.PROBLEMS[0]
    ctx = types.SimpleNamespace(user_data={'row_comp': rowc, 'problem': prob}, bot=DummyBot())
    update = DummyUpdate('Описание проблемы')
    state = await bot.custom_desc_handler(update, ctx)
    assert state == bot.ConversationHandler.END
    assert 'Запрос #99' in update.message.replies[0]
    assert called['args'][0] == rowc
    assert called['args'][1] == prob
    assert ctx.bot.sent


@pytest.mark.asyncio
async def test_custom_desc_handler_cancel(bot):
    class DummyMessage:
        def __init__(self, text):
            self.text = text
            self.replies = []

        async def reply_text(self, text, reply_markup=None):
            self.replies.append(text)

    class DummyUpdate:
        def __init__(self, text):
            self.message = DummyMessage(text)

    ctx = types.SimpleNamespace(user_data={})
    update = DummyUpdate('Отмена')
    state = await bot.custom_desc_handler(update, ctx)
    assert state == bot.ConversationHandler.END
    assert 'Отменено' in update.message.replies[0]


@pytest.mark.asyncio
async def test_clear_requests_admin_unauthorized(bot, monkeypatch):
    class DummyBot:
        def __init__(self):
            self.sent = []

        async def send_message(self, chat_id, text, reply_markup=None):
            self.sent.append(text)

    called = False

    async def fake_clear_requests():
        nonlocal called
        called = True

    monkeypatch.setattr(bot.db, 'clear_requests', fake_clear_requests)

    class DummyChat:
        def __init__(self, chat_id):
            self.id = chat_id

    class DummyUpdate:
        def __init__(self, chat_id):
            self.effective_chat = DummyChat(chat_id)

    ctx = types.SimpleNamespace(bot=DummyBot())
    update = DummyUpdate(999)
    await bot.clear_requests_admin(update, ctx)
    assert called is False
    assert ctx.bot.sent == []
