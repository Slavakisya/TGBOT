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


@pytest.fixture
def admin(utils):
    if 'helpdesk_bot.handlers.admin' in sys.modules:
        del sys.modules['helpdesk_bot.handlers.admin']
    return importlib.import_module('helpdesk_bot.handlers.admin')


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


@pytest.mark.asyncio
async def test_daily_message_admin_flow(monkeypatch, tmp_path):
    monkeypatch.setenv('HELPDESK_DB_PATH', str(tmp_path / 'tickets.db'))
    monkeypatch.setenv('TELEGRAM_TOKEN', 'T')
    monkeypatch.setenv('ADMIN_IDS', '1')

    for name in [
        'helpdesk_bot.db',
        'helpdesk_bot.utils',
        'helpdesk_bot.handlers.admin',
        'helpdesk_bot.daily',
    ]:
        sys.modules.pop(name, None)

    db_mod = importlib.import_module('helpdesk_bot.db')
    await db_mod.init_db()
    admin_mod = importlib.import_module('helpdesk_bot.handlers.admin')

    class DummyMessage:
        def __init__(self, text):
            self.text = text
            self.replies = []

        async def reply_text(self, text, reply_markup=None):
            self.replies.append(text)

    class DummyUser:
        def __init__(self, user_id):
            self.id = user_id

    class DummyUpdate:
        counter = 0

        def __init__(self, text):
            DummyUpdate.counter += 1
            self.message = DummyMessage(text)
            self.effective_user = DummyUser(1)
            self.update_id = DummyUpdate.counter

    ctx = types.SimpleNamespace(user_data={}, application=types.SimpleNamespace(job_queue=None))
    update_start = DummyUpdate('start')
    await admin_mod.daily_message_start(update_start, ctx)
    assert ctx.user_data[admin_mod.DAILY_STATE_KEY] == admin_mod.DAILY_STATE_MENU
    assert any('ежедневные сообщения' in msg.lower() for msg in update_start.message.replies)

    update_add = DummyUpdate('Добавить сообщение')
    await admin_mod.daily_message_menu(update_add, ctx)
    assert ctx.user_data[admin_mod.DAILY_STATE_KEY] == admin_mod.DAILY_STATE_ADD_TIME
    assert any('время отправки' in msg.lower() for msg in update_add.message.replies)

    update_time = DummyUpdate('09:30')
    await admin_mod.daily_message_save(update_time, ctx)
    assert ctx.user_data[admin_mod.DAILY_STATE_KEY] == admin_mod.DAILY_STATE_ADD_TEXT
    assert any('текст нового сообщения' in msg.lower() for msg in update_time.message.replies)

    update_text = DummyUpdate('Новое напоминание')
    await admin_mod.daily_message_save(update_text, ctx)
    assert ctx.user_data[admin_mod.DAILY_STATE_KEY] == admin_mod.DAILY_STATE_SELECTED
    assert any('сообщение добавлено' in msg.lower() for msg in update_text.message.replies)

    messages = await db_mod.list_daily_messages()
    assert len(messages) == 1
    message_id = messages[0]['id']
    assert messages[0]['text'] == 'Новое напоминание'
    assert messages[0]['send_time'] == '09:30'
    assert not messages[0]['disable_preview']
    assert messages[0]['parse_mode'] == ''

    update_format = DummyUpdate('Форматирование')
    await admin_mod.daily_message_menu(update_format, ctx)
    assert ctx.user_data[admin_mod.DAILY_STATE_KEY] == admin_mod.DAILY_STATE_FORMAT

    update_choose_format = DummyUpdate('Markdown')
    await admin_mod.daily_message_set_format(update_choose_format, ctx)
    assert ctx.user_data[admin_mod.DAILY_STATE_KEY] == admin_mod.DAILY_STATE_SELECTED
    msg = await db_mod.get_daily_message(message_id)
    assert msg['parse_mode'] == 'Markdown'

    update_toggle_preview = DummyUpdate('Переключить предпросмотр')
    await admin_mod.daily_message_menu(update_toggle_preview, ctx)
    msg = await db_mod.get_daily_message(message_id)
    assert msg['disable_preview'] is True

    update_change_time = DummyUpdate('Изменить время')
    await admin_mod.daily_message_menu(update_change_time, ctx)
    assert ctx.user_data[admin_mod.DAILY_STATE_KEY] == admin_mod.DAILY_STATE_EDIT_TIME

    update_new_time = DummyUpdate('10:15')
    await admin_mod.daily_message_save(update_new_time, ctx)
    msg = await db_mod.get_daily_message(message_id)
    assert msg['send_time'] == '10:15'
    assert ctx.user_data[admin_mod.DAILY_STATE_KEY] == admin_mod.DAILY_STATE_SELECTED

    update_change_text = DummyUpdate('Изменить текст')
    await admin_mod.daily_message_menu(update_change_text, ctx)
    assert ctx.user_data[admin_mod.DAILY_STATE_KEY] == admin_mod.DAILY_STATE_EDIT

    update_clear = DummyUpdate('Пусто')
    await admin_mod.daily_message_save(update_clear, ctx)
    msg = await db_mod.get_daily_message(message_id)
    assert msg['text'] == ''
    assert ctx.user_data[admin_mod.DAILY_STATE_KEY] == admin_mod.DAILY_STATE_SELECTED

    update_delete = DummyUpdate('Удалить сообщение')
    await admin_mod.daily_message_menu(update_delete, ctx)
    assert ctx.user_data[admin_mod.DAILY_STATE_KEY] == admin_mod.DAILY_STATE_MENU
    assert await db_mod.list_daily_messages() == []


@pytest.mark.asyncio
async def test_send_daily_message(monkeypatch, tmp_path):
    monkeypatch.setenv('HELPDESK_DB_PATH', str(tmp_path / 'tickets.db'))
    monkeypatch.setenv('TELEGRAM_TOKEN', 'T')
    monkeypatch.setenv('ADMIN_IDS', '1')

    for name in [
        'helpdesk_bot.db',
        'helpdesk_bot.utils',
        'helpdesk_bot.handlers.admin',
        'helpdesk_bot.daily',
    ]:
        sys.modules.pop(name, None)

    db_mod = importlib.import_module('helpdesk_bot.db')
    await db_mod.init_db()
    daily_mod = importlib.import_module('helpdesk_bot.daily')

    await db_mod.set_setting('daily_message_chat_id', '123')
    message_id = await db_mod.add_daily_message(
        'Привет',
        send_time='09:00',
        parse_mode='Markdown',
        disable_preview=True,
    )

    class DummyBot:
        def __init__(self):
            self.sent = []

        async def send_message(self, chat_id, text, parse_mode=None, disable_web_page_preview=None):
            self.sent.append((chat_id, text, parse_mode, disable_web_page_preview))

    job = types.SimpleNamespace(data={'message_id': message_id})
    ctx = types.SimpleNamespace(bot=DummyBot(), job=job)
    await daily_mod.send_daily_message(ctx)
    assert ctx.bot.sent == [(123, 'Привет', 'Markdown', True)]

    ctx.bot.sent.clear()
    await db_mod.update_daily_message(message_id, text='')
    await daily_mod.send_daily_message(ctx)
    assert ctx.bot.sent == []


@pytest.mark.asyncio
async def test_admin_handle_reply_success(monkeypatch, admin):
    async def fake_get_ticket(ticket_id):
        return (ticket_id, 'row', 'prob', 'descr', 'User', 555, 'новый', '2025-01-01T00:00:00')

    sent_messages = []

    class DummyBot:
        async def send_message(self, chat_id, text, reply_markup=None):
            sent_messages.append((chat_id, text))

    class DummyMessage:
        def __init__(self, text):
            self.text = text
            self.replies = []

        async def reply_text(self, text, reply_markup=None):
            self.replies.append(text)

    class DummyUpdate:
        def __init__(self, text):
            self.message = DummyMessage(text)

    monkeypatch.setattr(admin.db, 'get_ticket', fake_get_ticket)

    ctx = types.SimpleNamespace(user_data={'reply_ticket': 7}, bot=DummyBot())
    update = DummyUpdate('Ответ админа')

    await admin.handle_reply(update, ctx)

    assert sent_messages == [(555, '💬 Ответ на запрос #7:\nОтвет админа')]
    assert any('ответ отправлен' in msg.lower() for msg in update.message.replies)
    assert 'reply_ticket' not in ctx.user_data


@pytest.mark.asyncio
async def test_admin_handle_reply_cancel(monkeypatch, admin):
    called = {}

    async def fake_cancel(update, ctx):
        called['cancelled'] = True

    monkeypatch.setattr(admin, 'cancel', fake_cancel)

    class DummyMessage:
        def __init__(self, text):
            self.text = text

    class DummyUpdate:
        def __init__(self, text):
            self.message = DummyMessage(text)

    ctx = types.SimpleNamespace(user_data={'reply_ticket': 3}, bot=None)
    update = DummyUpdate('Отмена')

    await admin.handle_reply(update, ctx)

    assert 'reply_ticket' not in ctx.user_data
    assert called['cancelled'] is True


@pytest.mark.asyncio
async def test_handle_feedback_text_success(monkeypatch, tickets):
    async def fake_get_ticket(ticket_id):
        return (ticket_id, '1', 'Проблема', 'Описание', 'User', 999, 'готово', '2025-01-01T00:00:00')

    async def fake_update_status(ticket_id, status):
        assert ticket_id == 5
        assert status == 'принято'

    sent_messages = []

    class DummyBot:
        async def send_message(self, chat_id, text, reply_markup=None):
            sent_messages.append((chat_id, text))

    class DummyMessage:
        def __init__(self, text):
            self.text = text
            self.replies = []

        async def reply_text(self, text, reply_markup=None):
            self.replies.append(text)

    class DummyUpdate:
        def __init__(self, text):
            self.message = DummyMessage(text)

    monkeypatch.setattr(tickets.db, 'get_ticket', fake_get_ticket)
    monkeypatch.setattr(tickets.db, 'update_status', fake_update_status)
    monkeypatch.setattr(tickets, 'ALL_ADMINS', [42])
    monkeypatch.setattr(tickets, 'format_kyiv_time', lambda ts: 'time')

    ctx = types.SimpleNamespace(user_data={'feedback_ticket': 5}, bot=DummyBot())
    update = DummyUpdate('Все еще не работает')

    await tickets.handle_feedback_text(update, ctx)

    assert any('фидбэк' in text.lower() for _, text in sent_messages)
    assert any('спасибо' in msg.lower() for msg in update.message.replies)
    assert 'feedback_ticket' not in ctx.user_data


@pytest.mark.asyncio
async def test_handle_feedback_text_cancel(monkeypatch, tickets):
    called = {}

    async def fake_cancel(update, ctx):
        called['cancelled'] = True

    monkeypatch.setattr(tickets, 'cancel', fake_cancel)

    class DummyMessage:
        def __init__(self, text):
            self.text = text

    class DummyUpdate:
        def __init__(self, text):
            self.message = DummyMessage(text)

    ctx = types.SimpleNamespace(user_data={'feedback_ticket': 9}, bot=None)
    update = DummyUpdate('Отмена')

    await tickets.handle_feedback_text(update, ctx)

    assert 'feedback_ticket' not in ctx.user_data
    assert called['cancelled'] is True
