# -*- coding: utf-8 -*-

import os
import logging
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from telegram import (
    Update,
    ReplyKeyboardMarkup,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    Application,              # v21
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

import db  # ваш локальный модуль рядом с bot.py

# startup-хук: подключаем БД, инициализируем её, отключаем webhook и печатаем кто мы
async def on_startup(app):
    app.bot_data["db_conn"] = await db.connect()
    await db.init_db()
    await app.bot.delete_webhook(drop_pending_updates=True)
    me = await app.bot.get_me()
    logging.getLogger("helpdesk_bot").info(
        f"✅ Logged in as @{me.username} ({me.id}). Polling…"
    )


async def on_shutdown(app):
    await db.close()

# логи
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s :: %(message)s",
)
log = logging.getLogger("helpdesk_bot")


# ───────────────────────────── НАСТРОЙКИ ──────────────────────────────────────
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ADMIN_CHAT_ID  = int(os.getenv("ADMIN_CHAT_ID", "0"))

# Добавь нужные ID сюда (можно расширять)
ADMIN_IDS = {
    ADMIN_CHAT_ID,
    7615248486,   # второй админ
    7923988594,   # третий админ
    8237445057,
}
ALL_ADMINS = [a for a in ADMIN_IDS if a]  # уберём нули, если переменная пустая

if not TELEGRAM_TOKEN or not ALL_ADMINS:
    raise RuntimeError("TELEGRAM_TOKEN или ADMIN_CHAT_ID(ы) не установлены")


def is_admin(user_id: int) -> bool:
    """Проверяет, является ли id администратора."""
    return user_id in ADMIN_IDS

# ─────────────────────────── СОСТОЯНИЯ FSM ───────────────────────────────────
(
    STATE_ROW,
    STATE_COMP,
    STATE_PROBLEM_MENU,
    STATE_CUSTOM_DESC,
    STATE_REPLY,
    STATE_BROADCAST,
    STATE_ARCHIVE_DATE,
    STATE_STATS_DATE,
    STATE_CRM_EDIT,
    STATE_FEEDBACK_TEXT,
) = range(10)

# ───────────────────────────── КОНСТАНТЫ ──────────────────────────────────────
PROBLEMS = [
    "Вопросы по тф",
    "Не работают уши",
    "Не работает микрофон",
    "Не открывается сайт",
    "Комп выключился/завис/сгорел",
    "Настройка шумодава",
    "Плохо работает комп",
    "Плохой инет (или его нет)",
    "Другая проблема",
]

STATUS_OPTIONS  = ["принято", "в работе", "готово", "отменено"]
USER_MAIN_MENU  = [["Создать запрос", "Мои запросы"], ["Справка"]]
ADMIN_MAIN_MENU = [
    ["Все запросы", "Архив запросов", "Статистика"],
    ["Очистить все запросы", "Отправить всем сообщение", "Изменить CRM"],
    ["Благодарности"],
]
CANCEL_KEYBOARD = ReplyKeyboardMarkup([["Отмена"]], resize_keyboard=True)

# ───────────────────────────── СПРАВКА ────────────────────────────────────────
HELP_TEXT_RULES = """📞 Правила пользования телефонией

⚠️ Триггеры в разговоре

🚫 Не говорите стоп-слова (война, путин, СВО и т. д.) — за это моментальный бан симки.
🚫 Избегайте командных слов: ❌ продиктуйте, зайдите, откройте  
✅ Говорите иначе: ✔️ необходимо продиктовать, вам нужно сказать

📌 Соблюдайте это, чтобы связь не обрывалась и SIP жил дольше.

⸻

❌ Категорически запрещено:

🚫 Автодозвон (интервал менее 10 сек).  
🤬 Мат (давить можно, но вежливо).  
⚖️ Политика (выборы, власть, международка).  
💣 Война и минирования (вопросы «чей Крым?» и т. д.).

⸻

✅ Как работать с SIP правильно:

⏳ Перерыв между звонками 30 сек.  
📵 Не звоните на один номер более 2–3 раз (кроме дефицита линий).  
🛑 Ошибка “All sockets busy now” → ждите 3–5 минут.  
📞 Проверяйте SIP на случайных номерах (такси, отели).  
📱 Занято/сервис с гудками = недозвон!!!!!  
📝 Отправили ошибку — ждите плюс и не звоните, пока вам не скажут.
"""

HELP_TEXT_LINKS = """https://docs.google.com/forms/d/1YKYwRaHv0yfhHZXU4BFNymwHDP2EZSZn7NYr05DLIfM/viewform?edit_requested=true4
https://fhd154.mamoth.cloud
https://google.com
https://yandex.eu/maps
http://t-r-o-n.ru
http://kykart.ru
https://numbase.ru
https://sanstv.ru
https://www.kody.su
https://fincalculator.ru/telefon/region-po-nomeru
https://chatgpt.com
https://checksnils.ru
https://проверка-паспорта.рф
https://proverk.ru
https://www.egrul.ru/inn
https://8sot.su
https://randomus.ru
https://2gis.ru
https://geostudy.ru/timemap.html
"""

HELP_TEXT_SPEECH = """Здравствуйте. Вас приветствует компания МГТС. Меня зовут Евгений.
(…длинный текст оставлен как есть…)"""

# ───────────────────────────── ВСПОМОГАТЕЛЬНОЕ ───────────────────────────────
def format_kyiv_time(ts: str) -> str:
    try:
        dt = datetime.fromisoformat(ts).replace(tzinfo=timezone.utc)
        return dt.astimezone(ZoneInfo("Europe/Kiev")).strftime("%Y-%m-%d %H:%M:%S")
    except Exception as e:
        log.warning("format_kyiv_time failed: %s", e)
        return ts

# ───────────────────────────── HANDLERS ───────────────────────────────────────
async def start_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    await db.add_user(u.id, u.full_name)
    menu = ADMIN_MAIN_MENU if u.id in ADMIN_IDS else USER_MAIN_MENU
    await update.message.reply_text("Привет! Выберите действие:",
                                    reply_markup=ReplyKeyboardMarkup(menu, resize_keyboard=True))
    return ConversationHandler.END

# — Создание запроса —
async def start_conversation(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Введите номер ряда (1–6):", reply_markup=CANCEL_KEYBOARD)
    return STATE_ROW

async def row_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    txt = update.message.text.strip()
    if txt == "Отмена":
        return await cancel(update, ctx)
    if not txt.isdigit() or not (1 <= int(txt) <= 6):
        await update.message.reply_text("Неверный ряд. Введите 1–6:", reply_markup=CANCEL_KEYBOARD)
        return STATE_ROW
    ctx.user_data["row"] = txt
    await update.message.reply_text("Введите номер компьютера:", reply_markup=CANCEL_KEYBOARD)
    return STATE_COMP

async def comp_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    txt = update.message.text.strip()
    if txt == "Отмена":
        return await cancel(update, ctx)
    row = int(ctx.user_data["row"])
    max_comp = 9 if row in (5, 6) else 10
    if not txt.isdigit() or not (1 <= int(txt) <= max_comp):
        await update.message.reply_text(f"Неверный комп. Введите 1–{max_comp}:", reply_markup=CANCEL_KEYBOARD)
        return STATE_COMP
    ctx.user_data["row"] = str(row)
    ctx.user_data["comp"] = txt
    ctx.user_data["row_comp"] = f"{row}/{txt}"
    kb = [PROBLEMS[i:i+2] for i in range(0, len(PROBLEMS), 2)] + [["Отмена"]]
    await update.message.reply_text(
        "Выберите тип проблемы:",
        reply_markup=ReplyKeyboardMarkup(kb, one_time_keyboard=True, resize_keyboard=True)
    )
    return STATE_PROBLEM_MENU

async def problem_menu_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    ch = update.message.text.strip()
    if ch == "Отмена":
        return await cancel(update, ctx)
    if ch not in PROBLEMS:
        await update.message.reply_text("Выберите проблему из списка:", reply_markup=CANCEL_KEYBOARD)
        return STATE_PROBLEM_MENU
    ctx.user_data["problem"] = ch
    await update.message.reply_text("Опишите свою проблему кратко:", reply_markup=CANCEL_KEYBOARD)
    return STATE_CUSTOM_DESC

async def custom_desc_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    txt = update.message.text.strip()
    if txt == "Отмена":
        return await cancel(update, ctx)
    ctx.user_data["description"] = txt
    return await send_request(update, ctx)

async def send_request(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    rowc = ctx.user_data["row_comp"]
    prob = ctx.user_data["problem"]
    desc = ctx.user_data["description"]
    user = update.effective_user

    req_id = await db.add_ticket(rowc, prob, desc, user.full_name, user.id)

    # пользователю
    await update.message.reply_text(
        f"✅ Запрос #{req_id} зарегистрирован.\nР/К: {rowc}\n{prob}. {desc}",
        reply_markup=ReplyKeyboardMarkup(USER_MAIN_MENU, resize_keyboard=True),
    )

    # админам
    btns_s  = [InlineKeyboardButton(s, callback_data=f"status:{req_id}:{s}")
               for s in STATUS_OPTIONS if s != "отменено"]
    btn_r   = InlineKeyboardButton("Ответить", callback_data=f"reply:{req_id}")
    created = format_kyiv_time((await db.get_ticket(req_id))[7])
    admin_text = (f"Новый запрос #{req_id}\n"
                  f"{rowc}: {prob}\n"
                  f"Описание: {desc}\n"
                  f"От: {user.full_name}, {created}")
    markup = InlineKeyboardMarkup([btns_s, [btn_r]])

    for aid in ALL_ADMINS:
        try:
            await ctx.bot.send_message(aid, admin_text, reply_markup=markup)
        except Exception as e:
            log.warning("Не удалось отправить админу %s: %s", aid, e)

    return ConversationHandler.END

# — Мои запросы —
async def my_requests(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid  = update.effective_user.id
    rowc = ctx.user_data.get("row_comp", "")
    all_r = await db.list_tickets()
    mine  = [r for r in all_r if r[5] == uid and r[1] == rowc]
    if not mine:
        await update.message.reply_text(
            f"У вас нет запросов для {rowc}.",
            reply_markup=ReplyKeyboardMarkup(USER_MAIN_MENU, resize_keyboard=True)
        )
        return
    btns = [[InlineKeyboardButton(f"#{r[0]} ({r[1]}) [{r[6]}] {r[2]}", callback_data=f"show:{r[0]}")]
            for r in mine]
    await update.message.reply_text("Ваши запросы — нажмите для подробностей:",
                                    reply_markup=InlineKeyboardMarkup(btns))

async def show_request(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    rid = int(q.data.split(":")[1])
    r   = await db.get_ticket(rid)
    rowc = ctx.user_data.get("row_comp", "")
    if not r or r[5] != q.from_user.id or r[1] != rowc:
        await q.edit_message_reply_markup(None)
        await q.message.reply_text("Не ваш запрос.",
                                   reply_markup=ReplyKeyboardMarkup(USER_MAIN_MENU, resize_keyboard=True))
        return
    await q.edit_message_reply_markup(None)
    created = format_kyiv_time(r[7])
    detail  = (f"#{rid} — {r[1]}\n"
               f"Проблема: {r[2]}\n"
               f"Статус: {r[6]}\n"
               f"Создано: {created}")
    if r[6] not in ("готово", "отменено"):
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("Отменить запрос", callback_data=f"cancel_req:{rid}")]])
        await q.message.reply_text(detail, reply_markup=kb)
    else:
        await q.message.reply_text(detail)
    await q.message.reply_text("Главное меню:",
                               reply_markup=ReplyKeyboardMarkup(USER_MAIN_MENU, resize_keyboard=True))

async def cancel_request_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    rid = int(q.data.split(":")[1])
    r   = await db.get_ticket(rid)
    if not r or r[5] != q.from_user.id:
        await q.edit_message_text("Не удалось отменить.")
        return
    await db.update_status(rid, "отменено")
    await q.edit_message_text(f"Запрос #{rid} отменён.")
    for aid in ALL_ADMINS:
        try:
            await ctx.bot.send_message(aid, f"🔔 Запрос #{rid} отменён пользователем {q.from_user.full_name}")
        except Exception as e:
            log.warning("Не удалось уведомить админа %s об отмене запроса #%s: %s", aid, rid, e)
    await ctx.bot.send_message(q.from_user.id, "Главное меню:",
                               reply_markup=ReplyKeyboardMarkup(USER_MAIN_MENU, resize_keyboard=True))

# — Ответ админа —
async def init_reply(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query
    await q.answer()
    rid = int(q.data.split(":")[1])
    ctx.user_data["reply_ticket"] = rid
    await q.message.reply_text(f"Введите ответ для запроса #{rid}:", reply_markup=CANCEL_KEYBOARD)
    return STATE_REPLY

async def handle_reply(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    txt = update.message.text.strip()
    if txt == "Отмена":
        return await cancel(update, ctx)
    rid = ctx.user_data.get("reply_ticket")
    tkt = await db.get_ticket(rid)
    if tkt:
        await ctx.bot.send_message(tkt[5], f"💬 Ответ на запрос #{rid}:\n{txt}")
        await update.message.reply_text("Ответ отправлен.",
                                        reply_markup=ReplyKeyboardMarkup(ADMIN_MAIN_MENU, resize_keyboard=True))
    else:
        await update.message.reply_text("Запрос не найден.",
                                        reply_markup=ReplyKeyboardMarkup(ADMIN_MAIN_MENU, resize_keyboard=True))
    return ConversationHandler.END

# — Рассылка —
async def init_broadcast(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Введите текст рассылки:", reply_markup=CANCEL_KEYBOARD)
    return STATE_BROADCAST

async def handle_broadcast(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    txt = update.message.text.strip()
    if txt == "Отмена":
        return await cancel(update, ctx)
    users = await db.list_users()
    sent = 0
    for uid in users:
        try:
            await ctx.bot.send_message(uid, f"📢 Админ рассылка:\n\n{txt}")
            sent += 1
        except Exception as e:
            log.warning("Не удалось отправить рассылку пользователю %s: %s", uid, e)
    await update.message.reply_text(
        f"Рассылка отправлена {sent} пользователям.",
        reply_markup=ReplyKeyboardMarkup(ADMIN_MAIN_MENU, resize_keyboard=True)
    )
    return ConversationHandler.END

# — Справка и CRM —
async def help_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    kb = [["Правила телефонии", "Ссылки для работы"], ["Спич", "CRM"], ["Назад"]]
    await update.message.reply_text("Выберите раздел справки:",
                                    reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))

async def rules_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(HELP_TEXT_RULES)
    await help_menu(update, ctx)

async def links_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(HELP_TEXT_LINKS)
    await help_menu(update, ctx)

async def speech_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(HELP_TEXT_SPEECH)
    await help_menu(update, ctx)

async def crm_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    raw = await db.get_setting("crm_text") or ""
    lines = []
    for ln in raw.splitlines():
        ln = ln.strip()
        if not ln:
            continue
        parts = ln.rsplit(" ", 2)
        if len(parts) == 3:
            name, team, code = parts
            lines.append(f"{name} ({team}) {code}")
        else:
            lines.append(ln)
    await update.message.reply_text("\n".join(lines) if lines else "CRM пуста.")
    await help_menu(update, ctx)

async def back_to_main(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    return await start_menu(update, ctx)

# — Изменить CRM —
async def edit_crm_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    if update.effective_user.id not in ADMIN_IDS:
        return ConversationHandler.END
    await update.message.reply_text("Введите весь текст CRM:", reply_markup=CANCEL_KEYBOARD)
    return STATE_CRM_EDIT

async def edit_crm_save(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    txt = update.message.text
    if txt == "Отмена":
        return await cancel(update, ctx)
    await db.set_setting("crm_text", txt)
    await update.message.reply_text("✅ CRM сохранена.",
                                    reply_markup=ReplyKeyboardMarkup(ADMIN_MAIN_MENU, resize_keyboard=True))
    return ConversationHandler.END

# — Админские разделы —
async def all_requests_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id not in ADMIN_IDS:
        return
    rows = await db.list_tickets()
    active = [r for r in rows if r[6] not in ("готово", "отменено")]
    if not active:
        await ctx.bot.send_message(update.effective_chat.id, "Нет активных запросов.")
        return
    for r in active:
        rid, rowc, prob, descr, uname, uid, st, cts = r
        created = format_kyiv_time(cts)
        btns_s = [InlineKeyboardButton(s, callback_data=f"status:{rid}:{s}")
                  for s in STATUS_OPTIONS if s != "отменено"]
        btn_r = InlineKeyboardButton("Ответить", callback_data=f"reply:{rid}")
        await ctx.bot.send_message(
            update.effective_chat.id,
            f"#{rid} [{st}]\n{rowc}: {prob}\nОписание: {descr}\nОт: {uname}, {created}",
            reply_markup=InlineKeyboardMarkup([btns_s, [btn_r]])
        )

async def init_archive(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Введите дату (ГГГГ-ММ-ДД):", reply_markup=CANCEL_KEYBOARD)
    return STATE_ARCHIVE_DATE

async def archive_date_invalid(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Неверный формат. Введите ГГГГ-ММ-ДД:", reply_markup=CANCEL_KEYBOARD)
    return STATE_ARCHIVE_DATE

async def archive_by_date_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    d = update.message.text.strip()
    all_r = await db.list_tickets()
    arch = [r for r in all_r if r[7].startswith(d) and r[6] in ("готово", "отменено")]
    if not arch:
        await update.message.reply_text(
            f"Нет запросов за {d}.",
            reply_markup=ReplyKeyboardMarkup(ADMIN_MAIN_MENU, resize_keyboard=True)
        )
    else:
        for r in arch:
            rid, rowc, prob, descr, uname, uid, st, cts = r
            c = format_kyiv_time(cts)
            await update.message.reply_text(f"#{rid} [{st}]\n{rowc}: {prob}\nОписание: {descr}\nОт: {uname}, {c}")
        await update.message.reply_text("Меню администратора:",
                                        reply_markup=ReplyKeyboardMarkup(ADMIN_MAIN_MENU, resize_keyboard=True))
    return ConversationHandler.END

async def stats_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "Введите период статистики (YYYY-MM-DD — YYYY-MM-DD):",
        reply_markup=CANCEL_KEYBOARD
    )
    return STATE_STATS_DATE

async def stats_show(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    txt = update.message.text.strip()
    if txt == "Отмена":
        return await cancel(update, ctx)
    parts = [p.strip() for p in txt.split("—")]
    if len(parts) != 2:
        await update.message.reply_text(
            "Неверный формат, используйте YYYY-MM-DD — YYYY-MM-DD",
            reply_markup=CANCEL_KEYBOARD
        )
        return STATE_STATS_DATE
    start_str, end_str = parts
    by_status  = await db.count_by_status(start_str, end_str)
    by_problem = await db.count_by_problem(start_str, end_str)
    lines = [f"📊 Стата с {start_str} по {end_str}:", "\nПо статусам:"]
    for st, cnt in by_status.items():
        lines.append(f"  • {st}: {cnt}")
    lines.append("\nПо типам проблем:")
    for pr, cnt in by_problem.items():
        lines.append(f"  • {pr}: {cnt}")
    await update.message.reply_text("\n".join(lines),
        reply_markup=ReplyKeyboardMarkup(ADMIN_MAIN_MENU, resize_keyboard=True))
    return ConversationHandler.END

async def status_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    _, rid_s, new_st = q.data.split(":")
    rid = int(rid_s)
    await db.update_status(rid, new_st)

    if new_st in ("готово", "отменено"):
        await q.edit_message_reply_markup(None)
        await q.edit_message_text(f"#{rid} — статус: «{new_st}»")
    else:
        btns_s = [InlineKeyboardButton(s, callback_data=f"status:{rid}:{s}")
                  for s in STATUS_OPTIONS if s != "отменено"]
        btn_r = InlineKeyboardButton("Ответить", callback_data=f"reply:{rid}")
        await q.edit_message_text(f"#{rid} — статус: «{new_st}»",
                                  reply_markup=InlineKeyboardMarkup([btns_s, [btn_r]]))

    tkt = await db.get_ticket(rid)
    if not tkt:
        return

    user_id = tkt[5]

    for aid in ALL_ADMINS:
        try:
            await ctx.bot.send_message(aid, f"🔔 Статус запроса #{rid} обновлён на «{new_st}»")
        except Exception as e:
            log.warning("Не удалось уведомить админа %s об обновлении статуса #%s: %s", aid, rid, e)

    try:
        await ctx.bot.send_message(user_id, f"🔔 Статус вашего запроса #{rid} обновлён: «{new_st}»")
    except Exception as e:
        log.exception("Не удалось уведомить пользователя %s о статусе #%s", user_id, rid, exc_info=e)
        for aid in ALL_ADMINS:
            try:
                await ctx.bot.send_message(aid, f"⚠️ Не удалось уведомить пользователя {user_id} об обновлении статуса запроса #{rid}")
            except Exception as e2:
                log.warning("Не удалось уведомить админа %s о сбое: %s", aid, e2)

    if new_st == "готово":
        fb_btn = InlineKeyboardButton("Проблема не решена", callback_data=f"feedback:{rid}")
        th_btn = InlineKeyboardButton("спасибо любимый айтишник <3", callback_data=f"thanks:{rid}")
        await ctx.bot.send_message(
            user_id,
            "Если проблема не решена или хотите поблагодарить, нажмите:",
            reply_markup=InlineKeyboardMarkup([[fb_btn, th_btn]])
        )

async def init_feedback(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query
    await q.answer()
    rid = int(q.data.split(":")[1])
    ctx.user_data["feedback_ticket"] = rid
    await q.message.reply_text("Опишите, пожалуйста, что осталось нерешённым:", reply_markup=CANCEL_KEYBOARD)
    return STATE_FEEDBACK_TEXT

async def handle_feedback_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    txt = update.message.text.strip()
    if txt == "Отмена":
        return await cancel(update, ctx)
    rid = ctx.user_data.get("feedback_ticket")
    tkt = await db.get_ticket(rid)
    if not tkt:
        await update.message.reply_text("Ошибка: запрос не найден.",
                                        reply_markup=ReplyKeyboardMarkup(USER_MAIN_MENU, resize_keyboard=True))
        return ConversationHandler.END

    await db.update_status(rid, "принято")

    for aid in ALL_ADMINS:
        try:
            await ctx.bot.send_message(aid, f"💬 Фидбэк к запросу #{rid}:\n{txt}")
            btns_s = [InlineKeyboardButton(s, callback_data=f"status:{rid}:{s}")
                      for s in STATUS_OPTIONS if s != "отменено"]
            btn_r = InlineKeyboardButton("Ответить", callback_data=f"reply:{rid}")
            created = format_kyiv_time(tkt[7])
            new_text = (f"🔄 Запрос #{rid} возвращён в «принято» после фидбека\n"
                        f"{tkt[1]}: {tkt[2]}\n"
                        f"Описание: {tkt[3]}\n"
                        f"От: {tkt[4]}, {created}")
            await ctx.bot.send_message(aid, new_text, reply_markup=InlineKeyboardMarkup([btns_s, [btn_r]]))
        except Exception as e:
            log.warning("Не удалось отправить фидбэк админу %s по запросу #%s: %s", aid, rid, e)

    await update.message.reply_text(
        "Спасибо за обратную связь! Возвращаемся в главное меню.",
        reply_markup=ReplyKeyboardMarkup(USER_MAIN_MENU, resize_keyboard=True)
    )
    return ConversationHandler.END

async def handle_thanks(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    rid = int(q.data.split(":")[1])
    tkt = await db.get_ticket(rid)
    if not tkt:
        await q.edit_message_text("Ошибка: запрос не найден.")
        return
    for aid in ALL_ADMINS:
        key = f"thanks_{aid}"
        old = await db.get_setting(key) or "0"
        cnt = int(old) + 1
        await db.set_setting(key, str(cnt))
        try:
            await ctx.bot.send_message(aid, f"🙏 Пользователь {q.from_user.full_name} поблагодарил за запрос #{rid}.")
        except Exception as e:
            log.warning("Не удалось отправить благодарность админу %s: %s", aid, e)
    await q.edit_message_text("Спасибо за благодарность! ❤")
    await ctx.bot.send_message(q.from_user.id, "Главное меню:",
                               reply_markup=ReplyKeyboardMarkup(USER_MAIN_MENU, resize_keyboard=True))

async def show_thanks_count(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    cnts = []
    for aid in ALL_ADMINS:
        v = await db.get_setting(f"thanks_{aid}") or "0"
        cnts.append(f"Admin {aid}: {v}")
    await update.message.reply_text(
        "Благодарности:\n" + "\n".join(cnts),
        reply_markup=ReplyKeyboardMarkup(ADMIN_MAIN_MENU, resize_keyboard=True)
    )

async def clear_requests_admin(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id not in ADMIN_IDS:
        return
    await db.clear_requests()
    await ctx.bot.send_message(update.effective_chat.id, "🔄 Все запросы удалены администратором.")

async def cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("❌ Отменено.",
                                    reply_markup=ReplyKeyboardMarkup(USER_MAIN_MENU, resize_keyboard=True))
    return ConversationHandler.END

# ───────────────────────────── ЗАПУСК ─────────────────────────────────────────
def main():
    app = (Application
           .builder()
           .token(TELEGRAM_TOKEN)
           .post_init(on_startup)
           .post_shutdown(on_shutdown)
           .build())
    # Conversations
    conv_ticket = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^Создать запрос$"), start_conversation)],
        states={
            STATE_ROW:          [MessageHandler(filters.Regex("^Отмена$"), cancel),
                                 MessageHandler(filters.TEXT & ~filters.COMMAND, row_handler)],
            STATE_COMP:         [MessageHandler(filters.Regex("^Отмена$"), cancel),
                                 MessageHandler(filters.TEXT & ~filters.COMMAND, comp_handler)],
            STATE_PROBLEM_MENU: [MessageHandler(filters.Regex("^Отмена$"), cancel),
                                 MessageHandler(filters.TEXT & ~filters.COMMAND, problem_menu_handler)],
            STATE_CUSTOM_DESC:  [MessageHandler(filters.Regex("^Отмена$"), cancel),
                                 MessageHandler(filters.TEXT & ~filters.COMMAND, custom_desc_handler)],
        },
        fallbacks=[CommandHandler("cancel", cancel),
                   MessageHandler(filters.Regex("^Отмена$"), cancel)],
    )

    conv_reply = ConversationHandler(
        entry_points=[CallbackQueryHandler(init_reply, pattern=r"^reply:\d+$")],
        states={STATE_REPLY: [MessageHandler(filters.Regex("^Отмена$"), cancel),
                              MessageHandler(filters.TEXT & ~filters.COMMAND, handle_reply)]},
        fallbacks=[CommandHandler("cancel", cancel),
                   MessageHandler(filters.Regex("^Отмена$"), cancel)],
    )

    conv_broadcast = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^Отправить всем сообщение$"), init_broadcast)],
        states={STATE_BROADCAST: [MessageHandler(filters.Regex("^Отмена$"), cancel),
                                  MessageHandler(filters.TEXT & ~filters.COMMAND, handle_broadcast)]},
        fallbacks=[CommandHandler("cancel", cancel),
                   MessageHandler(filters.Regex("^Отмена$"), cancel)],
    )

    conv_archive = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^Архив запросов$"), init_archive)],
        states={
            STATE_ARCHIVE_DATE: [
                MessageHandler(filters.Regex(r"^\d{4}-\d{2}-\d{2}$"), archive_by_date_handler),
                MessageHandler(filters.TEXT & ~filters.COMMAND, archive_date_invalid),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel),
                   MessageHandler(filters.Regex("^Отмена$"), cancel)],
    )

    conv_stats = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^Статистика$"), stats_start)],
        states={STATE_STATS_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, stats_show)]},
        fallbacks=[CommandHandler("cancel", cancel),
                   MessageHandler(filters.Regex("^Отмена$"), cancel)],
    )

    conv_crm = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^Изменить CRM$"), edit_crm_start)],
        states={STATE_CRM_EDIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_crm_save)]},
        fallbacks=[CommandHandler("cancel", cancel),
                   MessageHandler(filters.Regex("^Отмена$"), cancel)],
    )

    conv_feedback = ConversationHandler(
        entry_points=[CallbackQueryHandler(init_feedback, pattern=r"^feedback:\d+$")],
        states={STATE_FEEDBACK_TEXT: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_feedback_text),
            MessageHandler(filters.Regex("^Отмена$"), cancel)
        ]},
        fallbacks=[CommandHandler("cancel", cancel),
                   MessageHandler(filters.Regex("^Отмена$"), cancel)],
    )

    # register conversation handlers
    app.add_handler(conv_ticket)
    app.add_handler(conv_reply)
    app.add_handler(conv_broadcast)
    app.add_handler(conv_archive)
    app.add_handler(conv_stats)
    app.add_handler(conv_crm)
    app.add_handler(conv_feedback)

    # Команды/меню
    app.add_handler(CommandHandler("start", start_menu))
    app.add_handler(MessageHandler(filters.Regex("^Мои запросы$"), my_requests))

    # Справка
    app.add_handler(MessageHandler(filters.Regex("^Справка$"), help_menu))
    app.add_handler(MessageHandler(filters.Regex("^Правила телефонии$"), rules_handler))
    app.add_handler(MessageHandler(filters.Regex("^Ссылки для работы$"), links_handler))
    app.add_handler(MessageHandler(filters.Regex("^Спич$"), speech_handler))
    app.add_handler(MessageHandler(filters.Regex("^CRM$"), crm_handler))
    app.add_handler(MessageHandler(filters.Regex("^Назад$"), back_to_main))

    # Админ-разделы
    app.add_handler(MessageHandler(filters.Regex("^Все запросы$"), all_requests_cmd))
    app.add_handler(MessageHandler(filters.Regex("^Очистить все запросы$"), clear_requests_admin))
    app.add_handler(MessageHandler(filters.Regex("^Благодарности$"), show_thanks_count))

    # Callback’и
    app.add_handler(CallbackQueryHandler(show_request, pattern=r"^show:\d+$"))
    app.add_handler(CallbackQueryHandler(cancel_request_callback, pattern=r"^cancel_req:\d+$"))
    app.add_handler(CallbackQueryHandler(status_callback, pattern=r"^status:\d+:"))
    app.add_handler(CallbackQueryHandler(handle_thanks, pattern=r"^thanks:\d+$"))

    log.info("🚀 Bot starting polling…")
    app.run_polling(close_loop=False)

if __name__ == "__main__":
    main()
