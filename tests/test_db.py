import pytest
import aiosqlite
from helpdesk_bot import db


@pytest.mark.asyncio
async def test_init_db_creates_tables_and_settings(temp_db):
    await db.init_db()
    async with aiosqlite.connect(db.DB_PATH) as conn:
        cur = await conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {r[0] for r in await cur.fetchall()}
        assert {'tickets', 'users', 'settings'} <= tables

        cur = await conn.execute("PRAGMA table_info(tickets)")
        cols = {r[1] for r in await cur.fetchall()}
        assert {'row_comp', 'problem', 'description', 'user_name', 'user_id', 'status', 'created_at'} <= cols

        cur = await conn.execute("SELECT key FROM settings")
        settings = {r[0] for r in await cur.fetchall()}
        assert {'crm_text', 'speech_text', 'daily_message_text', 'daily_message_chat_id'} <= settings


@pytest.mark.asyncio
async def test_add_ticket(temp_db):
    await db.init_db()
    tid = await db.add_ticket('1/2', 'prob', 'desc', 'User', 42)
    ticket = await db.get_ticket(tid)
    assert ticket[1] == '1/2'
    assert ticket[2] == 'prob'
    assert ticket[3] == 'desc'
    assert ticket[4] == 'User'
    assert ticket[5] == 42
    assert ticket[6] == 'принято'


@pytest.mark.asyncio
async def test_update_status(temp_db):
    await db.init_db()
    tid = await db.add_ticket('1/2', 'prob', 'desc', 'User', 42)
    ok = await db.update_status(tid, 'в работе')
    assert ok
    ticket = await db.get_ticket(tid)
    assert ticket[6] == 'в работе'
