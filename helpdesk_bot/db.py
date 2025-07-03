# db.py

import aiosqlite

DB_PATH = "tickets.db"

async def init_db():
    """
    Создаёт таблицы tickets, users и settings, если их нет,
    и добавляет недостающие колонки в tickets.
    Также устанавливает дефолтный текст CRM в settings.
    """
    async with aiosqlite.connect(DB_PATH) as conn:
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
        default_crm = """МАРГАРИТА ЦЕНТРАЛ user001
ЖЕКА ЛЬВОВ user002
СОНЯ ШАРК user003
АНДРЕЙ КЛАН ШАРК user005
ВЛАД NEW ШАРК user006
АЛЕКСАНДРА ШАРК user007
ЮЛЯ ШАРК user008
АННА-МАРИЯ ШАРК user009
АДЕЛИНА ШАРК user010
ДЕН ТРОТИК ШАРК user012
РОМА NEW ШАРК user013
ДАВИД ШАРК user014
ИЛЬЯ КОСМОС ШАРК user015
ДАША ШАРК user016
АРТЕМ ШАРК user017
КАТЯ ШАРК user018
ДИМА БРОНКС user019
ПОКАШ БРОНКС user020
СТАС БРОНКС user021
КОЛЯ БРОНКС user022
ИЛЬЯ БРОНКС user023
МАША БРОНКС user024
МАРИНА БРОНКС user025
ТУРБО БРОНКС user026
САНЯ КРАСНЫЙ ЛЕГИОН user027
ТАНЯ ЯШИБА user028
ВЛАД ЯШИБА user029
АНЯ ЯШИБА user030
ЛЕРА Ф1 user031
РАМИН ТИМУР user032
МАРЧИК БЛИЗНЕЦЫ user033
ИГОРЬ БЛИЗНЕЦЫ user034
ИВАН БЛИЗНЕЦЫ user036
НАСТЯ NEW БЛИЗНЕЦЫ user037
ДЕНИС БЛИЗНЕЦЫ user038
САША КЭП БЛИЗНЕЦЫ user039
БОДЯ NEW БЛИЗНЕЦЫ user040
СЁМА БЛИЗНЕЦЫ user041
ЗМЕЙ БЛИЗНЕЦЫ user042
БЕССМЕРТНЫЙ БЛИЗНЕЦЫ user043
ОРЕСТ БЛИЗНЕЦЫ user044
МИША БОРЩАГА БЛИЗНЕЦЫ user045
ТЯПА БЛИЗНЕЦЫ user047
МАЛЮТИН БЛИЗНЕЦЫ user048
ТЁМА БЛИЗНЕЦЫ user049
БОГОМОЛ БЛИЗНЕЦЫ user050
БАНЗАЙ БЛИЗНЕЦЫ user051
САША КИПИШ СПАРТА user052
ВАДИМ МУХА СПАРТА user053
ЯРИК NEW СПАРТА user054
ЛЕРА NEW СПАРТА user055
АНДРЕЙ РИККИ СПАРТА user056
ДИАНА СПАРТА user057
АРТЕМ ДАН СПАРТА user058
ВАНЯ СПАРТА user060
НИКИТА ГИК СПАРТА user062
МАКС КЫЛЫМ СПАРТА user063
ДАРИНА СПАРТА user064
СВЯТОСЛАВ СВЯТОЙ СПАРТА user065
ВОВА МАЛЫШ СПАРТА user066
КИРИЛЛ ГОРЬКИЙ СПАРТА user067
НЕКИТ ЖИВЧИК СПАРТА user068
АРТЕМ ФОСФОР СПАРТА user069
КИРИЛЛ NEW СПАРТА user071
ГЕНА СПАРТА user072
ЛИЛ СПАРТА user073
ЖЕКА СПАРТА user074
ЛЕНА-ГЕНА СПАРТА user075
СЕРГЕЙ СПАРТА user076
АНДРЕЙ СПАРТА user077
НАСТЯ ЛАКИ СПАРТА user078
ВЕРОНА СПАРТА user079
ИГОРЬ СПАРТА user080
МИША NEW СПАРТА user081
ЛЫСЫЙ АНДРЕЙ СПАРТА user082
ТИМУР СПАРТА user083
ГЕРАЛЬТ БЛИЗНЕЦЫ user084
СЛАВИК К-39 user085
ДИМОН К-39 user086
КАТЯ NEW СПАРТА user088
ЭЛЯ NEW СПАРТА user089
ВЛАД ХОСЕ К-39 user092
ИГОРЬ К-39 user093
ЮЛЯ NEW СПАРТА user094
ВЛАД ВАДЯ СПАРТА user095
ЛЁЛЯ ШАРК user096
ВАЛЕРИЯ NEW СПАРТА user097
ДИМА РАТ ШАРК user099
ДЕНИС NEW БЛИЗНЕЦЫ user101
АЛЕКСЕЙ NEW БЛИЗНЕЦЫ user102
ДАРИНА NEW ДАШОН СПАРТА user103
ДАНЯ NEW БЛИЗНЕЦЫ user104
ЖЕНЯ КАРАНДАШ БЛИЗНЕЦЫ user105
САША ШУХЕР БЛИЗНЕЦЫ user106
НАСТЯ СПАРТА user107
КОЛЯ NEW СПАРТА user108
ИЛЬЯ ДЛИННЫЙ ШАРК user109
АНТОН ЛЫСЫЙ ШАРК user110
ДИАНА СПАРТА user111
ВЛАД ДИЛЕР К-39 user112
НАТАША БУРАЯ СПАРТА user113
ПАША NEW ШАРК user114
РУСЛАН ГУСЬ ШАРК user115
АЛИНА NEW ШАРК user116
КОЛЯ ДОБРЫЙ ШАРК user117
ВИТАЛИК ШАРК user118
ВЛАД РЖАВЫЙ БЛИЗНЕЦЫ user119
АРТЕМ БОКС ШАРК user120
ВОВА ПЕРВЫЙ К-39 user121
НАЗАР МОЦЯ К-39 user122
АНЯ NEW ШАРК user123
МАРИАННА (ТИМУР) user124
САНЯ NEW КИНЗО user125
МАША NEW (ТИМУР) user126
ТИМОФЕЙ (БРОНКС) user127
ЭЛЯ (БРОНКС) user128
ГЛЕБ (КИНЗО) user129
"""
        await conn.execute(
            "INSERT OR IGNORE INTO settings(key, value) VALUES(?, ?)",
            ("crm_text", default_crm)
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
            (key, value)
        )
        await conn.commit()

async def add_user(user_id: int, full_name: str):
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute(
            "INSERT OR IGNORE INTO users(id, full_name) VALUES(?,?)",
            (user_id, full_name)
        )
        await conn.commit()

async def list_users() -> list[int]:
    async with aiosqlite.connect(DB_PATH) as conn:
        cur = await conn.execute("SELECT id FROM users")
        return [r[0] for r in await cur.fetchall()]

async def add_ticket(row_comp: str, problem: str, description: str, user_name: str, user_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as conn:
        cur = await conn.execute(
            "INSERT INTO tickets(row_comp, problem, description, user_name, user_id) VALUES(?,?,?,?,?)",
            (row_comp, problem, description, user_name, user_id)
        )
        await conn.commit()
        return cur.lastrowid

async def list_tickets() -> list[tuple]:
    async with aiosqlite.connect(DB_PATH) as conn:
        cur = await conn.execute("""
            SELECT id, row_comp, problem, description, user_name, user_id, status, created_at
              FROM tickets
             ORDER BY id DESC
        """)
        return await cur.fetchall()

async def get_ticket(ticket_id: int) -> tuple | None:
    async with aiosqlite.connect(DB_PATH) as conn:
        cur = await conn.execute("""
            SELECT id, row_comp, problem, description, user_name, user_id, status, created_at
              FROM tickets
             WHERE id = ?
        """, (ticket_id,))
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

async def count_by_status(start_date: str, end_date: str) -> dict[str,int]:
    async with aiosqlite.connect(DB_PATH) as conn:
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
    async with aiosqlite.connect(DB_PATH) as conn:
        cur = await conn.execute(
            """
            SELECT problem, COUNT(*) 
              FROM tickets 
             WHERE DATE(created_at) BETWEEN ? AND ?
             GROUP BY problem
            """, (start_date, end_date)
        )
        return {p: c for p, c in await cur.fetchall()}
