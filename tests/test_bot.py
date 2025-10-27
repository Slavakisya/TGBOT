import types
import importlib
import sys
import sqlite3
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


@pytest.fixture
def predictions(utils):
    if 'helpdesk_bot.predictions' in sys.modules:
        del sys.modules['helpdesk_bot.predictions']
    return importlib.import_module('helpdesk_bot.predictions')


@pytest.mark.asyncio
async def test_start_menu_private_admin(tickets, monkeypatch):
    class DummyMessage:
        def __init__(self):
            self.replies = []
            self.reply_markup = None

        async def reply_text(self, text, reply_markup=None):
            self.replies.append(text)
            self.reply_markup = reply_markup

    class DummyUpdate:
        def __init__(self, user_id, chat_type):
            self.message = DummyMessage()
            self.effective_user = types.SimpleNamespace(id=user_id, full_name='Admin User')
            self.effective_chat = types.SimpleNamespace(id=100, type=chat_type)

    class DummyBot:
        def __init__(self):
            self.sent = []

        async def send_message(self, chat_id, text, reply_markup=None):
            self.sent.append((chat_id, text, reply_markup))

    async def fake_add_user(user_id, full_name):
        return None

    monkeypatch.setattr(tickets.db, 'add_user', fake_add_user)

    ctx = types.SimpleNamespace(user_data={}, bot=DummyBot())
    update = DummyUpdate(user_id=1, chat_type='private')

    state = await tickets.start_menu(update, ctx)

    assert state == tickets.ConversationHandler.END
    assert update.message.reply_markup.keyboard == tickets.ADMIN_MAIN_MENU
    assert ctx.bot.sent == []


@pytest.mark.asyncio
async def test_start_menu_group_admin_prompt(tickets, monkeypatch):
    class DummyMessage:
        def __init__(self):
            self.replies = []
            self.reply_markup = None

        async def reply_text(self, text, reply_markup=None):
            self.replies.append(text)
            self.reply_markup = reply_markup

    class DummyUpdate:
        def __init__(self, user_id, chat_type):
            self.message = DummyMessage()
            self.effective_user = types.SimpleNamespace(id=user_id, full_name='Admin User')
            self.effective_chat = types.SimpleNamespace(id=-100, type=chat_type)

    class DummyBot:
        def __init__(self):
            self.sent = []

        async def send_message(self, chat_id, text, reply_markup=None):
            self.sent.append((chat_id, text, reply_markup))

    async def fake_add_user(user_id, full_name):
        return None

    monkeypatch.setattr(tickets.db, 'add_user', fake_add_user)

    ctx = types.SimpleNamespace(user_data={}, bot=DummyBot())
    update = DummyUpdate(user_id=1, chat_type='supergroup')

    state = await tickets.start_menu(update, ctx)

    assert state == tickets.ConversationHandler.END
    assert update.message.reply_markup.keyboard == tickets.USER_MAIN_MENU
    assert ctx.bot.sent
    sent_chat_id, sent_text, sent_markup = ctx.bot.sent[0]
    assert sent_chat_id == 1
    assert 'личном чате' in sent_text
    assert sent_markup.keyboard == tickets.ADMIN_MAIN_MENU
    assert ctx.user_data['admin_private_prompt_sent'] is True


@pytest.mark.asyncio
async def test_start_menu_group_regular_user(tickets, monkeypatch):
    class DummyMessage:
        def __init__(self):
            self.replies = []
            self.reply_markup = None

        async def reply_text(self, text, reply_markup=None):
            self.replies.append(text)
            self.reply_markup = reply_markup

    class DummyUpdate:
        def __init__(self, user_id, chat_type):
            self.message = DummyMessage()
            self.effective_user = types.SimpleNamespace(id=user_id, full_name='User')
            self.effective_chat = types.SimpleNamespace(id=-100, type=chat_type)

    class DummyBot:
        def __init__(self):
            self.sent = []

        async def send_message(self, chat_id, text, reply_markup=None):
            self.sent.append((chat_id, text, reply_markup))

    async def fake_add_user(user_id, full_name):
        return None

    monkeypatch.setattr(tickets.db, 'add_user', fake_add_user)

    ctx = types.SimpleNamespace(user_data={}, bot=DummyBot())
    update = DummyUpdate(user_id=42, chat_type='group')

    state = await tickets.start_menu(update, ctx)

    assert state == tickets.ConversationHandler.END
    assert update.message.reply_markup.keyboard == tickets.USER_MAIN_MENU
    assert ctx.bot.sent == []
    assert 'admin_private_prompt_sent' not in ctx.user_data


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


def test_invalid_admin_ids_logged(monkeypatch, caplog):
    monkeypatch.setenv('TELEGRAM_TOKEN', 'T')
    monkeypatch.setenv('ADMIN_IDS', '1, abc, 3,42,xyz')

    if 'helpdesk_bot.utils' in sys.modules:
        del sys.modules['helpdesk_bot.utils']

    with caplog.at_level(logging.WARNING, logger='helpdesk_bot'):
        utils = importlib.import_module('helpdesk_bot.utils')

    assert utils.ADMIN_IDS == {1, 3, 42}
    assert 'Некорректные значения ADMIN_IDS игнорированы: abc, xyz' in caplog.text


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
        def __init__(self, text, photo=None):
            self.text = text
            self.photo = photo or []
            self.replies = []
            self.photo_replies = []

        async def reply_text(self, text, reply_markup=None):
            self.replies.append(text)

        async def reply_photo(self, photo, caption=None, parse_mode=None):
            self.photo_replies.append((photo, caption, parse_mode))

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
        def __init__(self, text, photo=None):
            self.text = text
            self.photo = photo or []
            self.replies = []
            self.photo_replies = []

        async def reply_text(self, text, reply_markup=None):
            self.replies.append(text)

        async def reply_photo(self, photo, caption=None, parse_mode=None):
            self.photo_replies.append((photo, caption, parse_mode))

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
        def __init__(self, text, photo=None):
            self.text = text
            self.photo = photo or []
            self.replies = []
            self.photo_replies = []

        async def reply_text(self, text, reply_markup=None):
            self.replies.append(text)

        async def reply_photo(self, photo, caption=None, parse_mode=None):
            self.photo_replies.append((photo, caption, parse_mode))

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
        def __init__(self, text, photo=None):
            self.text = text
            self.photo = photo or []
            self.replies = []
            self.photo_replies = []

        async def reply_text(self, text, reply_markup=None):
            self.replies.append(text)

        async def reply_photo(self, photo, caption=None, parse_mode=None):
            self.photo_replies.append((photo, caption, parse_mode))

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
        def __init__(self, text, photo=None):
            self.text = text
            self.photo = photo or []
            self.replies = []
            self.photo_replies = []

        async def reply_text(self, text, reply_markup=None):
            self.replies.append(text)

        async def reply_photo(self, photo, caption=None, parse_mode=None):
            self.photo_replies.append((photo, caption, parse_mode))

    class DummyUser:
        def __init__(self, user_id):
            self.id = user_id

    class DummyUpdate:
        counter = 0

        def __init__(self, text, photo=None):
            DummyUpdate.counter += 1
            self.message = DummyMessage(text, photo)
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
    assert ctx.user_data[admin_mod.DAILY_STATE_KEY] == admin_mod.DAILY_STATE_ADD_PHOTO
    assert any('сообщение добавлено' in msg.lower() for msg in update_text.message.replies)

    update_skip_photo = DummyUpdate('Пропустить')
    await admin_mod.daily_message_save(update_skip_photo, ctx)
    assert ctx.user_data[admin_mod.DAILY_STATE_KEY] == admin_mod.DAILY_STATE_SELECTED
    assert any('картинка' in msg.lower() for msg in update_skip_photo.message.replies)

    messages = await db_mod.list_daily_messages()
    assert len(messages) == 1
    message_id = messages[0]['id']
    assert messages[0]['text'] == 'Новое напоминание'
    assert messages[0]['send_time'] == '09:30'
    assert not messages[0]['disable_preview']
    assert messages[0]['parse_mode'] == ''
    assert messages[0]['photo_file_id'] == ''

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

    update_change_photo = DummyUpdate('Изменить картинку')
    await admin_mod.daily_message_menu(update_change_photo, ctx)
    assert ctx.user_data[admin_mod.DAILY_STATE_KEY] == admin_mod.DAILY_STATE_EDIT_PHOTO

    update_photo = DummyUpdate('', photo=[types.SimpleNamespace(file_id='photo123')])
    await admin_mod.daily_message_save_photo(update_photo, ctx)
    msg = await db_mod.get_daily_message(message_id)
    assert msg['photo_file_id'] == 'photo123'
    assert ctx.user_data[admin_mod.DAILY_STATE_KEY] == admin_mod.DAILY_STATE_SELECTED

    update_preview = DummyUpdate('Предпросмотр')
    await admin_mod.daily_message_menu(update_preview, ctx)
    assert ('photo123', None, 'Markdown') in update_preview.message.photo_replies

    update_change_photo_again = DummyUpdate('Изменить картинку')
    await admin_mod.daily_message_menu(update_change_photo_again, ctx)
    assert ctx.user_data[admin_mod.DAILY_STATE_KEY] == admin_mod.DAILY_STATE_EDIT_PHOTO

    update_remove_photo = DummyUpdate('Удалить фото')
    await admin_mod.daily_message_save(update_remove_photo, ctx)
    msg = await db_mod.get_daily_message(message_id)
    assert msg['photo_file_id'] == ''
    assert ctx.user_data[admin_mod.DAILY_STATE_KEY] == admin_mod.DAILY_STATE_SELECTED

    update_delete = DummyUpdate('Удалить сообщение')
    await admin_mod.daily_message_menu(update_delete, ctx)
    assert ctx.user_data[admin_mod.DAILY_STATE_KEY] == admin_mod.DAILY_STATE_MENU
    assert await db_mod.list_daily_messages() == []


@pytest.mark.asyncio
async def test_daily_message_back_button_variations(monkeypatch, tmp_path):
    monkeypatch.setenv('HELPDESK_DB_PATH', str(tmp_path / 'tickets.db'))
    monkeypatch.setenv('TELEGRAM_TOKEN', 'T')
    monkeypatch.setenv('ADMIN_IDS', '1')

    for name in [
        'helpdesk_bot.db',
        'helpdesk_bot.utils',
        'helpdesk_bot.handlers.admin',
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

    update_back = DummyUpdate('\u2B05 Назад')
    await admin_mod.daily_message_menu(update_back, ctx)
    assert ctx.user_data.get(admin_mod.DAILY_STATE_KEY) is None
    assert any('настройки' in msg.lower() for msg in update_back.message.replies)

@pytest.mark.asyncio
async def test_daily_message_menu_allows_admin_shortcuts(monkeypatch, tmp_path):
    monkeypatch.setenv('HELPDESK_DB_PATH', str(tmp_path / 'tickets.db'))
    monkeypatch.setenv('TELEGRAM_TOKEN', 'T')
    monkeypatch.setenv('ADMIN_IDS', '1')

    for name in [
        'helpdesk_bot.db',
        'helpdesk_bot.utils',
        'helpdesk_bot.handlers.admin',
    ]:
        sys.modules.pop(name, None)

    importlib.import_module('helpdesk_bot.db')
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

    shortcuts = [
        'Заявки',
        'Аналитика',
        'Настройки',
        'Все запросы',
        'Архив запросов',
        'Очистить все запросы',
        'Статистика',
        'Благодарности',
        'Изменить CRM',
        'Изменить спич',
    ]

    states = [
        admin_mod.DAILY_STATE_MENU,
        admin_mod.DAILY_STATE_SELECT,
        admin_mod.DAILY_STATE_SELECTED,
        admin_mod.DAILY_STATE_ADD_TIME,
        admin_mod.DAILY_STATE_ADD_TEXT,
        admin_mod.DAILY_STATE_EDIT,
        admin_mod.DAILY_STATE_EDIT_TIME,
        admin_mod.DAILY_STATE_FORMAT,
    ]

    for state in states:
        for text in shortcuts:
            ctx = types.SimpleNamespace(user_data={}, application=types.SimpleNamespace(job_queue=None))
            ctx.user_data[admin_mod.DAILY_STATE_KEY] = state
            ctx.user_data[admin_mod.DAILY_SELECTED_KEY] = 42
            ctx.user_data[admin_mod.DAILY_NEW_TIME_KEY] = '09:00'
            ctx.user_data[admin_mod.DAILY_SKIP_KEY] = 999

            update = DummyUpdate(text)
            await admin_mod.daily_message_menu(update, ctx)

            assert admin_mod.DAILY_STATE_KEY not in ctx.user_data
            assert admin_mod.DAILY_SELECTED_KEY not in ctx.user_data
            assert admin_mod.DAILY_NEW_TIME_KEY not in ctx.user_data
            assert admin_mod.DAILY_SKIP_KEY not in ctx.user_data
            assert update.message.replies == []


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
            self.photos = []

        async def send_message(self, chat_id, text, parse_mode=None, disable_web_page_preview=None):
            self.sent.append((chat_id, text, parse_mode, disable_web_page_preview))

        async def send_photo(self, chat_id, photo, caption=None, parse_mode=None):
            self.photos.append((chat_id, photo, caption, parse_mode))

    job = types.SimpleNamespace(data={'message_id': message_id})
    ctx = types.SimpleNamespace(bot=DummyBot(), job=job)
    await daily_mod.send_daily_message(ctx)
    assert ctx.bot.sent == [(123, 'Привет', 'Markdown', True)]
    assert ctx.bot.photos == []

    ctx.bot.sent.clear()
    ctx.bot.photos.clear()
    await db_mod.update_daily_message(message_id, photo_file_id='photo123')
    await daily_mod.send_daily_message(ctx)
    assert ctx.bot.sent == []
    assert ctx.bot.photos == [(123, 'photo123', 'Привет', 'Markdown')]

    ctx.bot.photos.clear()
    await db_mod.update_daily_message(message_id, text='', photo_file_id='')
    await daily_mod.send_daily_message(ctx)
    assert ctx.bot.sent == []
    assert ctx.bot.photos == []


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
async def test_predictions_table_autocreation(monkeypatch, tmp_path):
    monkeypatch.setenv('TELEGRAM_TOKEN', 'T')
    monkeypatch.setenv('ADMIN_IDS', '1')
    monkeypatch.setenv('HELPDESK_DB_PATH', str(tmp_path / 'auto.db'))

    sys.modules.pop('helpdesk_bot.db', None)

    db_mod = importlib.import_module('helpdesk_bot.db')

    predictions = await db_mod.list_predictions()
    assert predictions == []

    with sqlite3.connect(tmp_path / 'auto.db') as conn:
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='predictions'"
        )
        assert cursor.fetchone() is not None


@pytest.mark.asyncio
async def test_predictions_menu_normalizes_buttons(monkeypatch, tmp_path):
    monkeypatch.setenv('TELEGRAM_TOKEN', 'T')
    monkeypatch.setenv('ADMIN_IDS', '1')
    monkeypatch.setenv('HELPDESK_DB_PATH', str(tmp_path / 'preds.db'))

    for name in [
        'helpdesk_bot.db',
        'helpdesk_bot.utils',
        'helpdesk_bot.handlers.admin',
    ]:
        sys.modules.pop(name, None)

    db_mod = importlib.import_module('helpdesk_bot.db')
    admin_mod = importlib.import_module('helpdesk_bot.handlers.admin')

    await db_mod.init_db()

    class DummyMessage:
        def __init__(self, text):
            self.text = text
            self.replies: list[str] = []

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

    update_start = DummyUpdate('Предсказания')
    await admin_mod.predictions_start(update_start, ctx)
    assert ctx.user_data[admin_mod.PREDICTION_STATE_KEY] == admin_mod.PREDICTION_STATE_MENU

    update_repeat = DummyUpdate('Предсказания')
    handled_repeat = await admin_mod.predictions_menu(update_repeat, ctx)
    assert handled_repeat is True
    assert ctx.user_data[admin_mod.PREDICTION_STATE_KEY] == admin_mod.PREDICTION_STATE_MENU
    assert update_repeat.message.replies == []

    update_add = DummyUpdate('  Добавить   предсказание  ')
    await admin_mod.predictions_menu(update_add, ctx)
    assert ctx.user_data[admin_mod.PREDICTION_STATE_KEY] == admin_mod.PREDICTION_STATE_ADD
    assert any('нового предсказания' in msg.lower() for msg in update_add.message.replies)

    update_save = DummyUpdate('Первое предсказание')
    handled_save = await admin_mod.predictions_menu(update_save, ctx)
    assert handled_save is False
    await admin_mod.predictions_save(update_save, ctx)
    assert ctx.user_data[admin_mod.PREDICTION_STATE_KEY] == admin_mod.PREDICTION_STATE_MENU
    predictions = await db_mod.list_predictions()
    assert len(predictions) == 1

    update_config = DummyUpdate(' Настроить   предсказание ')
    await admin_mod.predictions_menu(update_config, ctx)
    assert ctx.user_data[admin_mod.PREDICTION_STATE_KEY] == admin_mod.PREDICTION_STATE_SELECT
    assert any('доступные предсказания' in msg.lower() for msg in update_config.message.replies)

    update_select = DummyUpdate('1')
    await admin_mod.predictions_menu(update_select, ctx)
    assert ctx.user_data[admin_mod.PREDICTION_STATE_KEY] == admin_mod.PREDICTION_STATE_SELECTED
    assert any('#1' in msg for msg in update_select.message.replies)

    update_edit = DummyUpdate('  Изменить   текст  ')
    await admin_mod.predictions_menu(update_edit, ctx)
    assert ctx.user_data[admin_mod.PREDICTION_STATE_KEY] == admin_mod.PREDICTION_STATE_EDIT
    assert any('новый текст' in msg.lower() for msg in update_edit.message.replies)


@pytest.mark.asyncio
async def test_predictions_menu_shows_random_sample(monkeypatch, tmp_path):
    monkeypatch.setenv('TELEGRAM_TOKEN', 'T')
    monkeypatch.setenv('ADMIN_IDS', '1')
    monkeypatch.setenv('HELPDESK_DB_PATH', str(tmp_path / 'preds_random.db'))

    for name in [
        'helpdesk_bot.db',
        'helpdesk_bot.utils',
        'helpdesk_bot.handlers.admin',
    ]:
        sys.modules.pop(name, None)

    db_mod = importlib.import_module('helpdesk_bot.db')
    admin_mod = importlib.import_module('helpdesk_bot.handlers.admin')

    await db_mod.init_db()
    texts = ['Первое предсказание', 'Второе предсказание', 'Третье предсказание']
    for text in texts:
        await db_mod.add_prediction(text)

    captured = {}

    def fake_sample(seq, k):
        captured['seq'] = list(seq)
        captured['k'] = k
        return list(reversed(seq[:k]))

    monkeypatch.setattr(admin_mod.random, 'sample', fake_sample)

    class DummyMessage:
        def __init__(self, text):
            self.text = text
            self.replies: list[str] = []

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

    update_start = DummyUpdate('Предсказания')
    await admin_mod.predictions_start(update_start, ctx)

    assert captured['k'] == min(5, len(captured['seq']))
    text = update_start.message.replies[-1]
    assert 'Случайные записи:' in text

    preview_lines = [
        line
        for line in text.splitlines()
        if line and line[0].isdigit() and '. ' in line
    ]
    assert preview_lines == [
        '3. Третье предсказание',
        '2. Второе предсказание',
        '1. Первое предсказание',
    ]


@pytest.mark.asyncio
async def test_predictions_menu_passthrough_for_text(monkeypatch, tmp_path):
    monkeypatch.setenv('TELEGRAM_TOKEN', 'T')
    monkeypatch.setenv('ADMIN_IDS', '1')
    monkeypatch.setenv('HELPDESK_DB_PATH', str(tmp_path / 'preds_passthrough.db'))

    for name in [
        'helpdesk_bot.db',
        'helpdesk_bot.utils',
        'helpdesk_bot.handlers.admin',
    ]:
        sys.modules.pop(name, None)

    db_mod = importlib.import_module('helpdesk_bot.db')
    admin_mod = importlib.import_module('helpdesk_bot.handlers.admin')

    await db_mod.init_db()

    class DummyMessage:
        def __init__(self, text):
            self.text = text
            self.replies: list[str] = []

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

    update_start = DummyUpdate('Предсказания')
    await admin_mod.predictions_start(update_start, ctx)

    update_add = DummyUpdate('Добавить предсказание')
    handled = await admin_mod.predictions_menu(update_add, ctx)
    assert handled is True
    assert ctx.user_data[admin_mod.PREDICTION_STATE_KEY] == admin_mod.PREDICTION_STATE_ADD
    assert any('нового предсказания' in msg.lower() for msg in update_add.message.replies)

    update_text = DummyUpdate('Новое предсказание')
    handled = await admin_mod.predictions_menu(update_text, ctx)
    assert handled is False

    await admin_mod.predictions_save(update_text, ctx)
    predictions = await db_mod.list_predictions()
    assert [p['text'] for p in predictions] == ['Новое предсказание']


@pytest.mark.asyncio
async def test_predictions_menu_ignores_buttons_during_text_entry(monkeypatch, tmp_path):
    monkeypatch.setenv('TELEGRAM_TOKEN', 'T')
    monkeypatch.setenv('ADMIN_IDS', '1')
    monkeypatch.setenv('HELPDESK_DB_PATH', str(tmp_path / 'preds_text_entry.db'))

    for name in [
        'helpdesk_bot.db',
        'helpdesk_bot.utils',
        'helpdesk_bot.handlers.admin',
    ]:
        sys.modules.pop(name, None)

    db_mod = importlib.import_module('helpdesk_bot.db')
    admin_mod = importlib.import_module('helpdesk_bot.handlers.admin')

    await db_mod.init_db()

    class DummyMessage:
        def __init__(self, text):
            self.text = text
            self.replies: list[str] = []

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

    await admin_mod.predictions_start(DummyUpdate('Предсказания'), ctx)

    update_add = DummyUpdate('Добавить предсказание')
    await admin_mod.predictions_menu(update_add, ctx)
    assert ctx.user_data[admin_mod.PREDICTION_STATE_KEY] == admin_mod.PREDICTION_STATE_ADD

    update_menu_button = DummyUpdate('Изменить текст')
    handled = await admin_mod.predictions_menu(update_menu_button, ctx)
    assert handled is True
    assert ctx.user_data[admin_mod.PREDICTION_STATE_KEY] == admin_mod.PREDICTION_STATE_ADD
    assert any('текст нового предсказания' in msg.lower() for msg in update_menu_button.message.replies)
    await admin_mod.predictions_save(update_menu_button, ctx)
    assert await db_mod.list_predictions() == []

    update_final_add = DummyUpdate('Первое предсказание')
    handled_final_add = await admin_mod.predictions_menu(update_final_add, ctx)
    assert handled_final_add is False
    await admin_mod.predictions_save(update_final_add, ctx)

    update_config = DummyUpdate('Настроить предсказание')
    await admin_mod.predictions_menu(update_config, ctx)

    await admin_mod.predictions_menu(DummyUpdate('1'), ctx)
    await admin_mod.predictions_menu(DummyUpdate('Изменить текст'), ctx)
    assert ctx.user_data[admin_mod.PREDICTION_STATE_KEY] == admin_mod.PREDICTION_STATE_EDIT

    update_during_edit = DummyUpdate('Добавить предсказание')
    handled = await admin_mod.predictions_menu(update_during_edit, ctx)
    assert handled is True
    assert ctx.user_data[admin_mod.PREDICTION_STATE_KEY] == admin_mod.PREDICTION_STATE_EDIT
    assert any('новый текст предсказания' in msg.lower() for msg in update_during_edit.message.replies)

    prediction_before = await db_mod.get_prediction(1)
    assert prediction_before['text'] == 'Первое предсказание'

    await admin_mod.predictions_save(update_during_edit, ctx)

    update_final_edit = DummyUpdate('Обновлённое предсказание')
    handled_final_edit = await admin_mod.predictions_menu(update_final_edit, ctx)
    assert handled_final_edit is False
    await admin_mod.predictions_save(update_final_edit, ctx)

    prediction_after = await db_mod.get_prediction(1)
    assert prediction_after['text'] == 'Обновлённое предсказание'

@pytest.mark.asyncio
async def test_wish_command_without_predictions(predictions, monkeypatch):
    async def fake_random():
        return None

    monkeypatch.setattr(predictions.db, 'get_random_prediction', fake_random)

    class DummyMessage:
        def __init__(self):
            self.replies = []

        async def reply_text(self, text):
            self.replies.append(text)

    message = DummyMessage()
    chat = types.SimpleNamespace(type="group")
    update = types.SimpleNamespace(
        effective_chat=chat,
        effective_message=message,
        message=message,
    )
    ctx = types.SimpleNamespace()

    await predictions.wish_command(update, ctx)

    assert message.replies == ["Предсказаний пока нет."]


@pytest.mark.asyncio
async def test_wish_command_with_prediction(predictions, monkeypatch):
    async def fake_random():
        return "  Улыбнись миру  "

    monkeypatch.setattr(predictions.db, 'get_random_prediction', fake_random)

    class DummyMessage:
        def __init__(self):
            self.replies = []

        async def reply_text(self, text):
            self.replies.append(text)

    message = DummyMessage()
    chat = types.SimpleNamespace(type="group")
    update = types.SimpleNamespace(
        effective_chat=chat,
        effective_message=message,
        message=message,
    )
    ctx = types.SimpleNamespace()

    await predictions.wish_command(update, ctx)

    assert message.replies == ["Улыбнись миру"]


@pytest.mark.asyncio
async def test_broadcast_predictions(predictions, monkeypatch):
    async def fake_list_predictions():
        return [
            {"id": 1, "text": "Счастья и удачи"},
        ]

    async def fake_list_users():
        return [101, 202]

    monkeypatch.setattr(predictions.db, 'list_predictions', fake_list_predictions)
    monkeypatch.setattr(predictions.db, 'list_users', fake_list_users)
    monkeypatch.setattr(predictions.random, 'choice', lambda seq: seq[0])

    sent = []

    class DummyBot:
        async def send_message(self, user_id, text):
            sent.append((user_id, text))

    ctx = types.SimpleNamespace(bot=DummyBot())

    await predictions.broadcast_predictions(ctx)

    assert sent == [(101, "Счастья и удачи"), (202, "Счастья и удачи")]


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
