import types
from datetime import timezone, timedelta
import pytest


def test_format_kyiv_time(bot, monkeypatch):
    monkeypatch.setattr(bot, 'ZoneInfo', lambda name: timezone(timedelta(hours=2)))
    ts = '2023-03-01 10:00:00'
    assert bot.format_kyiv_time(ts) == '2023-03-01 12:00:00'
    assert bot.format_kyiv_time('invalid') == 'invalid'


@pytest.mark.asyncio
async def test_row_handler_valid(bot):
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
    state = await bot.row_handler(update, ctx)
    assert state == bot.STATE_COMP
    assert ctx.user_data['row'] == '3'
    assert 'Введите номер компьютера' in update.message.replies[0]


@pytest.mark.asyncio
async def test_comp_handler_valid(bot):
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
    state = await bot.comp_handler(update, ctx)
    assert state == bot.STATE_PROBLEM_MENU
    assert ctx.user_data['row_comp'] == '3/5'
    assert 'Выберите тип проблемы' in update.message.replies[0]
