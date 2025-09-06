# db.py

import aiosqlite
import logging
from pathlib import Path

DB_PATH = "tickets.db"

CRM_PATH = Path(__file__).resolve().parent / "data" / "default_crm.txt"

_conn: aiosqlite.Connection | None = None
log = logging.getLogger(__name__)


async def connect() -> aiosqlite.Connection:
    """Создаёт или возвращает существующее соединение с базой данных."""
    global _conn
    if _conn is None:
        _conn = await aiosqlite.connect(DB_PATH)
    return _conn


async def close() -> None:
    """Закрывает глобальное соединение с базой данных."""
    global _conn
    if _conn is not None:
        await _conn.close()
        _conn = None


async def init_db():
    """
    Создаёт таблицы tickets, users и settings, если их нет,
    и добавляет недостающие колонки в tickets.
    Также устанавливает дефолтный текст CRM в settings.
    """
    conn = await connect()
    # tickets
    await conn.execute("""
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
    """)
    cursor = await conn.execute("PRAGMA table_info(tickets)")
    cols = [r[1] for r in await cursor.fetchall()]
    if "problem" not in cols:
        await conn.execute("ALTER TABLE tickets ADD COLUMN problem TEXT NOT NULL DEFAULT ''")
    # users
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            full_name TEXT
        )
    """)
    # settings (для CRM и будущих настроек)
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key   TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    # дефолтный CRM-текст
    try:
        default_crm = CRM_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        log.error("CRM data file not found: %s", CRM_PATH)
        default_crm = ""
    await conn.execute(
        "INSERT OR IGNORE INTO settings(key, value) VALUES(?, ?)",
        ("crm_text", default_crm)
    )
    await conn.commit()

async def get_setting(key: str) -> str | None:
    conn = await connect()
    cur = await conn.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = await cur.fetchone()
    return row[0] if row else None

async def set_setting(key: str, value: str):
    conn = await connect()
    await conn.execute(
        "INSERT INTO settings(key,value) VALUES(?,?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, value)
    )
    await conn.commit()

async def add_user(user_id: int, full_name: str):
    conn = await connect()
    await conn.execute(
        "INSERT OR IGNORE INTO users(id, full_name) VALUES(?,?)",
        (user_id, full_name)
    )
    await conn.commit()

async def list_users() -> list[int]:
    conn = await connect()
    cur = await conn.execute("SELECT id FROM users")
    return [r[0] for r in await cur.fetchall()]

async def add_ticket(row_comp: str, problem: str, description: str, user_name: str, user_id: int) -> int:
    conn = await connect()
    cur = await conn.execute(
        "INSERT INTO tickets(row_comp, problem, description, user_name, user_id) VALUES(?,?,?,?,?)",
        (row_comp, problem, description, user_name, user_id)
    )
    await conn.commit()
    return cur.lastrowid

async def list_tickets() -> list[tuple]:
    conn = await connect()
    cur = await conn.execute("""
        SELECT id, row_comp, problem, description, user_name, user_id, status, created_at
          FROM tickets
         ORDER BY id DESC
    """)
    return await cur.fetchall()

async def get_ticket(ticket_id: int) -> tuple | None:
    conn = await connect()
    cur = await conn.execute("""
        SELECT id, row_comp, problem, description, user_name, user_id, status, created_at
          FROM tickets
         WHERE id = ?
    """, (ticket_id,))
    return await cur.fetchone()

async def update_status(ticket_id: int, new_status: str) -> bool:
    conn = await connect()
    cur = await conn.execute(
        "UPDATE tickets SET status = ? WHERE id = ?", (new_status, ticket_id)
    )
    await conn.commit()
    return cur.rowcount > 0

async def clear_requests() -> None:
    conn = await connect()
    await conn.execute("DELETE FROM tickets")
    await conn.commit()

async def count_by_status(start_date: str, end_date: str) -> dict[str,int]:
    conn = await connect()
    cur = await conn.execute(
        """
        SELECT status, COUNT(*)
          FROM tickets
         WHERE DATE(created_at) BETWEEN ? AND ?
         GROUP BY status
        """, (start_date, end_date)
    )
    return {s: c for s, c in await cur.fetchall()}

async def count_by_problem(start_date: str, end_date: str) -> dict[str,int]:
    conn = await connect()
    cur = await conn.execute(
        """
        SELECT problem, COUNT(*)
          FROM tickets
         WHERE DATE(created_at) BETWEEN ? AND ?
         GROUP BY problem
        """, (start_date, end_date)
    )
    return {p: c for p, c in await cur.fetchall()}
