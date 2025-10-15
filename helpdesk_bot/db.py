# db.py

import os
import aiosqlite
import logging
from pathlib import Path

DB_PATH = Path(os.environ.get("HELPDESK_DB_PATH", Path(__file__).with_name("tickets.db")))

CRM_PATH = Path(__file__).resolve().parent / "data" / "default_crm.txt"
SPEECH_PATH = Path(__file__).resolve().parent / "data" / "default_speech.txt"

log = logging.getLogger(__name__)


async def init_db():
    """
    Создаёт таблицы tickets, users и settings, если их нет,
    и добавляет недостающие колонки в tickets.
    Также устанавливает дефолтные тексты CRM и спича в settings.
    """
    async with aiosqlite.connect(DB_PATH) as conn:
        # tickets
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                row_comp    TEXT    NOT NULL,
                problem     TEXT    NOT NULL DEFAULT '',
                description TEXT    NOT NULL DEFAULT '',
                user_name   TEXT,
                user_id     INTEGER,
                status      TEXT    NOT NULL DEFAULT 'принято',
                created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cursor = await conn.execute("PRAGMA table_info(tickets)")
        cols = [r[1] for r in await cursor.fetchall()]
        if "problem" not in cols:
            await conn.execute(
                "ALTER TABLE tickets ADD COLUMN problem TEXT NOT NULL DEFAULT ''"
            )
        # users
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                full_name TEXT
            )
            """
        )
        # settings (для CRM и будущих настроек)
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS settings (
                key   TEXT PRIMARY KEY,
                value TEXT
            )
            """
        )
        # дефолтные тексты CRM и спича
        try:
            default_crm = CRM_PATH.read_text(encoding="utf-8")
        except FileNotFoundError:
            log.error("CRM data file not found: %s", CRM_PATH)
            default_crm = ""
        try:
            default_speech = SPEECH_PATH.read_text(encoding="utf-8")
        except FileNotFoundError:
            log.error("Speech data file not found: %s", SPEECH_PATH)
            default_speech = ""
        await conn.executemany(
            "INSERT OR IGNORE INTO settings(key, value) VALUES(?, ?)",
            [
                ("crm_text", default_crm),
                ("speech_text", default_speech),
                ("daily_message_text", ""),
                ("daily_message_chat_id", ""),
            ],
        )
        await conn.commit()


async def get_setting(key: str) -> str | None:
    async with aiosqlite.connect(DB_PATH) as conn:
        cur = await conn.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = await cur.fetchone()
        return row[0] if row else None


async def set_setting(key: str, value: str):
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute(
            "INSERT INTO settings(key,value) VALUES(?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )
        await conn.commit()


async def add_user(user_id: int, full_name: str):
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute(
            "INSERT OR IGNORE INTO users(id, full_name) VALUES(?,?)",
            (user_id, full_name),
        )
        await conn.commit()


async def list_users() -> list[int]:
    async with aiosqlite.connect(DB_PATH) as conn:
        cur = await conn.execute("SELECT id FROM users")
        return [r[0] for r in await cur.fetchall()]


async def add_ticket(
    row_comp: str,
    problem: str,
    description: str,
    user_name: str,
    user_id: int,
) -> int:
    async with aiosqlite.connect(DB_PATH) as conn:
        cur = await conn.execute(
            "INSERT INTO tickets(row_comp, problem, description, user_name, user_id) VALUES(?,?,?,?,?)",
            (row_comp, problem, description, user_name, user_id),
        )
        await conn.commit()
        return cur.lastrowid


async def list_tickets() -> list[tuple]:
    async with aiosqlite.connect(DB_PATH) as conn:
        cur = await conn.execute(
            """
            SELECT id, row_comp, problem, description, user_name, user_id, status, created_at
              FROM tickets
             ORDER BY id DESC
            """
        )
        return await cur.fetchall()


async def get_ticket(ticket_id: int) -> tuple | None:
    async with aiosqlite.connect(DB_PATH) as conn:
        cur = await conn.execute(
            """
            SELECT id, row_comp, problem, description, user_name, user_id, status, created_at
              FROM tickets
             WHERE id = ?
            """,
            (ticket_id,),
        )
        return await cur.fetchone()


async def update_status(ticket_id: int, new_status: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as conn:
        cur = await conn.execute(
            "UPDATE tickets SET status = ? WHERE id = ?", (new_status, ticket_id)
        )
        await conn.commit()
        return cur.rowcount > 0


async def clear_requests() -> None:
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute("DELETE FROM tickets")
        await conn.commit()


async def count_by_status(start_date: str, end_date: str) -> dict[str, int]:
    async with aiosqlite.connect(DB_PATH) as conn:
        cur = await conn.execute(
            """
            SELECT status, COUNT(*)
              FROM tickets
             WHERE DATE(created_at) BETWEEN ? AND ?
             GROUP BY status
            """,
            (start_date, end_date),
        )
        return {s: c for s, c in await cur.fetchall()}


async def count_by_problem(start_date: str, end_date: str) -> dict[str, int]:
    async with aiosqlite.connect(DB_PATH) as conn:
        cur = await conn.execute(
            """
            SELECT problem, COUNT(*)
              FROM tickets
             WHERE DATE(created_at) BETWEEN ? AND ?
             GROUP BY problem
            """,
            (start_date, end_date),
        )
        return {p: c for p, c in await cur.fetchall()}
