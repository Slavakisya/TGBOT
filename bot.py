# bot.py

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
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)
import db

logging.basicConfig(level=logging.INFO)

TELEGRAM_TOKEN  = os.getenv("TELEGRAM_TOKEN")
ADMIN_CHAT_ID   = int(os.getenv("ADMIN_CHAT_ID", "0"))
SECOND_ADMIN_ID = 7615248486
ADMIN_IDS       = {ADMIN_CHAT_ID, SECOND_ADMIN_ID}
if not TELEGRAM_TOKEN or ADMIN_CHAT_ID == 0:
    raise RuntimeError("TELEGRAM_TOKEN или ADMIN_CHAT_ID не установлены")

# Состояния разговора
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
) = range(9)

# Постоянные списки
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
STATUS_OPTIONS = ["принято", "в работе", "готово", "отменено"]

USER_MAIN_MENU = [["Создать запрос", "Мои запросы"], ["Справка"]]
ADMIN_MAIN_MENU = [
    ["Все запросы", "Архив запросов", "Статистика"],
    ["Очистить все запросы", "Отправить всем сообщение", "Изменить CRM"],
]
CANCEL_KEYBOARD = ReplyKeyboardMarkup([["Отмена"]], resize_keyboard=True)

# Полные тексты справки
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
📵 Не звоните на один номер более 2–3 раз. Только если это не дефицит линий  
🛑 Ошибка “All sockets busy now” → ждите 3–5 минут.  
📞 Проверяйте SIP на случайных номерах (такси, отели).  
📱 Ошибка Занято/сервис с гудками = недозвон!!!!!  
📝 Отправили ошибку — ждите плюс и не звоните, пока вам не скажут.
"""

HELP_TEXT_LINKS = """https://forms.gle/iZPJjpdwXxSUq8bH7
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
"""

HELP_TEXT_SPEECH = """Здравствуйте. Вас приветствует компания МГТС. Меня зовут Евгений.  
Звоним касательно вашего городского номера. Должны предупредить вас, что с завтрашнего дня ваш городской номер будет отключен.

— Почему вы решили отказаться от городского телефона?  
— Я не отказываюсь.

— Почему тогда вы не обратились к нам на узел связи?  
— Я не знала.

Вам 5 января было направлено письмо по почте, вы его не получали?  
— Нет.

Проверяли почтовый ящик?  
— Ничего не было!

Видимо, Почта России снова подвела! Ладно, вы планируете пользоваться телефоном?  
Отключение номера происходит из-за замены оборудования на оптоволокно: префикс изменится с 7495 на 7499. Запишите новый номер!

(Диктую номер)

Сейчас замена линий происходит за счёт государства — вам платить не нужно. В течение 2 дней линии поменяют, качество связи станет лучше.

Те абоненты, которые отказываются от номера, смогут подать заявку на новый только через 2 месяца (оплачивая все услуги самостоятельно — мастер, оптоволокно, подключение; примерно 20 000 ₽).

После смены приходите в центр обслуживания за новыми документами и реквизитами. Для этого встаньте в электронную очередь:  
— На какую дату?  
— На 25.  
— До или после 12?  
— До 12.

Подтверждение придёт SMS на ваш мобильный номер:  
— 79….

По старому договору отображается:  
- Ф.И.О.  
- Дата рождения  
- Адрес  
— Всё верно?  
— Да.

Отправляем SMS с талоном.

По госпрограмме вам полагаются льготы (инвалидность, ветеран, донор, ребёнок войны).  
— У меня инвалидность.  
Вам скидка 60%. Для оформления подтвердите документ (паспорт или СНИЛС):  
— 5656 565 656.

Подойдите в центр за договором.

Есть семейный тариф — если оба пенсионеры, скидка ещё 50 ₽.  
— Я с мужем.

Переводим на льготное обслуживание, платёж 122 ₽. Для подтверждения скажите:  
«Я, ФИО, подтверждаю перевод на льготное обслуживание».  
— Я, ФИО, подтверждаю перевод на льготное обслуживание.

Готово! Если будут вопросы — обращайтесь на горячую линию.
"""

def format_kyiv_time(ts: str) -> str:
    try:
        dt = datetime.fromisoformat(ts).replace(tzinfo=timezone.utc)
        return dt.astimezone(ZoneInfo("Europe/Kiev")).strftime("%Y-%m-%d %H:%M:%S")
    except:
        return ts

# ─────────────────────────────────────────────────────────────────────────────
# Handlers

async def start_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await db.init_db()
    u = update.effective_user
    await db.add_user(u.id, u.full_name)
    menu = ADMIN_MAIN_MENU if u.id in ADMIN_IDS else USER_MAIN_MENU
    await update.message.reply_text("Привет! Выберите действие:", reply_markup=ReplyKeyboardMarkup(menu, resize_keyboard=True))
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
    ctx.user_data["comp"] = txt
    ctx.user_data["row_comp"] = f"{ctx.user_data['row']}/{txt}"
    kb = [PROBLEMS[i:i+2] for i in range(0, len(PROBLEMS), 2)] + [["Отмена"]]
    await update.message.reply_text("Выберите тип проблемы:", reply_markup=ReplyKeyboardMarkup(kb, one_time_keyboard=True, resize_keyboard=True))
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

    # уведомление пользователю
    await update.message.reply_text(
        f"✅ Запрос #{req_id} зарегистрирован.\nР/К: {rowc}\n{prob}. {desc}",
        reply_markup=ReplyKeyboardMarkup(USER_MAIN_MENU, resize_keyboard=True),
    )

    # уведомление админу
    recs = [SECOND_ADMIN_ID] if prob == "Вопросы по тф" else [ADMIN_CHAT_ID]
    btns_s = [InlineKeyboardButton(s, callback_data=f"status:{req_id}:{s}") for s in STATUS_OPTIONS if s != "отменено"]
    btn_r = InlineKeyboardButton("Ответить", callback_data=f"reply:{req_id}")
    created = format_kyiv_time((await db.get_ticket(req_id))[7])
    admin_text = f"Новый запрос #{req_id}\n{rowc}: {prob}\nОписание: {desc}\nОт: {user.full_name}, {created}"
    markup = InlineKeyboardMarkup([btns_s, [btn_r]])
    for aid in recs:
        await ctx.bot.send_message(aid, admin_text, reply_markup=markup)

    return ConversationHandler.END

# — Мои запросы —

async def my_requests(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    rowc = ctx.user_data.get("row_comp", "")
    all_r = await db.list_tickets()
    mine = [r for r in all_r if r[5] == uid and r[1] == rowc]
    if not mine:
        await update.message.reply_text(f"У вас нет запросов для {rowc}.", reply_markup=ReplyKeyboardMarkup(USER_MAIN_MENU, resize_keyboard=True))
        return
    btns = [[InlineKeyboardButton(f"#{r[0]} ({r[1]}) [{r[6]}] {r[2]}", callback_data=f"show:{r[0]}")] for r in mine]
    await update.message.reply_text("Ваши запросы — нажмите для подробностей:", reply_markup=InlineKeyboardMarkup(btns))

async def show_request(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    rid = int(q.data.split(":")[1])
    r = await db.get_ticket(rid)
    rowc = ctx.user_data.get("row_comp", "")
    if not r or r[5] != q.from_user.id or r[1] != rowc:
        await q.edit_message_reply_markup(None)
        await q.message.reply_text("Не ваш запрос.", reply_markup=ReplyKeyboardMarkup(USER_MAIN_MENU, resize_keyboard=True))
        return
    await q.edit_message_reply_markup(None)
    created = format_kyiv_time(r[7])
    detail = f"#{rid} — {r[1]}\nПроблема: {r[2]}\nСтатус: {r[6]}\nСоздано: {created}"
    if r[6] not in ("готово", "отменено"):
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("Отменить запрос", callback_data=f"cancel_req:{rid}")]])
        await q.message.reply_text(detail, reply_markup=kb)
    else:
        await q.message.reply_text(detail)
    await q.message.reply_text("Главное меню:", reply_markup=ReplyKeyboardMarkup(USER_MAIN_MENU, resize_keyboard=True))

async def cancel_request_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    rid = int(q.data.split(":")[1])
    r = await db.get_ticket(rid)
    if not r or r[5] != q.from_user.id:
        await q.edit_message_text("Не удалось отменить.")
        return
    await db.update_status(rid, "отменено")
    await q.edit_message_text(f"Запрос #{rid} отменён.")
    aid = SECOND_ADMIN_ID if r[2] == "Вопросы по тф" else ADMIN_CHAT_ID
    await ctx.bot.send_message(aid, f"🔔 Запрос #{rid} отменён пользователем {q.from_user.full_name}")
    await ctx.bot.send_message(q.from_user.id, "Главное меню:", reply_markup=ReplyKeyboardMarkup(USER_MAIN_MENU, resize_keyboard=True))

# — Ответ админа —

async def init_reply(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query; await q.answer()
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
        await update.message.reply_text("Ответ отправлен.", reply_markup=ReplyKeyboardMarkup(ADMIN_MAIN_MENU, resize_keyboard=True))
    else:
        await update.message.reply_text("Запрос не найден.", reply_markup=ReplyKeyboardMarkup(ADMIN_MAIN_MENU, resize_keyboard=True))
    return ConversationHandler.END

# — Рассылка —

async def init_broadcast(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Введите текст рассылки:", reply_markup=CANCEL_KEYBOARD)
    return STATE_BROADCAST

async def handle_broadcast(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    txt = update.message.text.strip()
    if txt == "Отмена":
        return await cancel(update, ctx)
    users = await db.list_users(); sent = 0
    for uid in users:
        try:
            await ctx.bot.send_message(uid, f"📢 Админ рассылка:\n\n{txt}")
            sent += 1
        except:
            pass
    await update.message.reply_text(f"Рассылка отправлена {sent} пользователям.", reply_markup=ReplyKeyboardMarkup(ADMIN_MAIN_MENU, resize_keyboard=True))
    return ConversationHandler.END

# — Справка и CRM —

async def help_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    kb = [
        ["Правила телефонии", "Ссылки для работы"],
        ["Спич",            "CRM"],
        ["Назад"]
    ]
    await update.message.reply_text("Выберите раздел справки:", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))

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
    await update.message.reply_text("\n".join(lines))
    await help_menu(update, ctx)

async def back_to_main(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await start_menu(update, ctx)

# — Изменить CRM —

async def edit_crm_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    if update.effective_user.id not in ADMIN_IDS:
        return
    await update.message.reply_text("Введите весь текст CRM:", reply_markup=CANCEL_KEYBOARD)
    return STATE_CRM_EDIT

async def edit_crm_save(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    txt = update.message.text
    if txt == "Отмена":
        return await cancel(update, ctx)
    await db.set_setting("crm_text", txt)
    await update.message.reply_text("✅ CRM сохранена.", reply_markup=ReplyKeyboardMarkup(ADMIN_MAIN_MENU, resize_keyboard=True))
    return ConversationHandler.END

# — Админ: все запросы, архив, статистика, очистка —

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
        btns_s = [InlineKeyboardButton(s, callback_data=f"status:{rid}:{s}") for s in STATUS_OPTIONS if s != "отменено"]
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
        await update.message.reply_text(f"Нет запросов за {d}.", reply_markup=ReplyKeyboardMarkup(ADMIN_MAIN_MENU, resize_keyboard=True))
    else:
        for r in arch:
            rid, rowc, prob, descr, uname, uid, st, cts = r
            c = format_kyiv_time(cts)
            await update.message.reply_text(f"#{rid} [{st}]\n{rowc}: {prob}\nОписание: {descr}\nОт: {uname}, {c}")
        await update.message.reply_text("Меню администратора:", reply_markup=ReplyKeyboardMarkup(ADMIN_MAIN_MENU, resize_keyboard=True))
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
        await update.message.reply_text("Неверный формат, используйте YYYY-MM-DD — YYYY-MM-DD", reply_markup=CANCEL_KEYBOARD)
        return STATE_STATS_DATE
    start_str, end_str = parts
    by_status = await db.count_by_status(start_str, end_str)
    by_problem = await db.count_by_problem(start_str, end_str)
    lines = [f"📊 Статистика с {start_str} по {end_str}:", "\nПо статусам:"]
    for st, cnt in by_status.items():
        lines.append(f"  • {st}: {cnt}")
    lines.append("\nПо типам проблем:")
    for pr, cnt in by_problem.items():
        lines.append(f"  • {pr}: {cnt}")
    await update.message.reply_text("\n".join(lines), reply_markup=ReplyKeyboardMarkup(ADMIN_MAIN_MENU, resize_keyboard=True))
    return ConversationHandler.END

async def status_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    _, rid_s, new_st = q.data.split(":"); rid = int(rid_s)
    await db.update_status(rid, new_st)
    if new_st in ("готово", "отменено"):
        await q.edit_message_reply_markup(None)
        await q.edit_message_text(f"#{rid} — статус: «{new_st}»")
    else:
        btns_s = [InlineKeyboardButton(s, callback_data=f"status:{rid}:{s}") for s in STATUS_OPTIONS if s != "отменено"]
        btn_r = InlineKeyboardButton("Ответить", callback_data=f"reply:{rid}")
        await q.edit_message_text(f"#{rid} — статус: «{new_st}»", reply_markup=InlineKeyboardMarkup([btns_s, [btn_r]]))
    tkt = await db.get_ticket(rid)
    if tkt:
        await ctx.bot.send_message(tkt[5], f"🔔 Статус вашего запроса #{rid} обновлён: «{new_st}»")

async def clear_requests_admin(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id not in ADMIN_IDS:
        return
    await db.clear_requests()
    await ctx.bot.send_message(update.effective_chat.id, "🔄 Все запросы удалены администратором.")

async def cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("❌ Отменено.", reply_markup=ReplyKeyboardMarkup(USER_MAIN_MENU, resize_keyboard=True))
    return ConversationHandler.END

# ─────────────────────────────────────────────────────────────────────────────
def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    # ConversationHandlers
    conv_ticket = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^Создать запрос$"), start_conversation)],
        states={
            STATE_ROW:          [MessageHandler(filters.Regex("^Отмена$"), cancel), MessageHandler(filters.TEXT & ~filters.COMMAND, row_handler)],
            STATE_COMP:         [MessageHandler(filters.Regex("^Отмена$"), cancel), MessageHandler(filters.TEXT & ~filters.COMMAND, comp_handler)],
            STATE_PROBLEM_MENU: [MessageHandler(filters.Regex("^Отмена$"), cancel), MessageHandler(filters.TEXT & ~filters.COMMAND, problem_menu_handler)],
            STATE_CUSTOM_DESC:  [MessageHandler(filters.Regex("^Отмена$"), cancel), MessageHandler(filters.TEXT & ~filters.COMMAND, custom_desc_handler)],
        },
        fallbacks=[CommandHandler("cancel", cancel), MessageHandler(filters.Regex("^Отмена$"), cancel)],
    )
    conv_reply = ConversationHandler(
        entry_points=[CallbackQueryHandler(init_reply, pattern=r"^reply:\d+$")],
        states={ STATE_REPLY: [ MessageHandler(filters.Regex("^Отмена$"), cancel), MessageHandler(filters.TEXT & ~filters.COMMAND, handle_reply) ] },
        fallbacks=[CommandHandler("cancel", cancel), MessageHandler(filters.Regex("^Отмена$"), cancel)],
    )
    conv_broadcast = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^Отправить всем сообщение$"), init_broadcast)],
        states={ STATE_BROADCAST: [ MessageHandler(filters.Regex("^Отмена$"), cancel), MessageHandler(filters.TEXT & ~filters.COMMAND, handle_broadcast) ] },
        fallbacks=[CommandHandler("cancel", cancel), MessageHandler(filters.Regex("^Отмена$"), cancel)],
    )
    conv_archive = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^Архив запросов$"), init_archive)],
        states={
            STATE_ARCHIVE_DATE:[
                MessageHandler(filters.Regex(r"^\d{4}-\d{2}-\d{2}$"), archive_by_date_handler),
                MessageHandler(filters.TEXT & ~filters.COMMAND, archive_date_invalid),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel), MessageHandler(filters.Regex("^Отмена$"), cancel)],
    )
    conv_stats = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^Статистика$"), stats_start)],
        states={ STATE_STATS_DATE: [ MessageHandler(filters.TEXT & ~filters.COMMAND, stats_show) ] },
        fallbacks=[CommandHandler("cancel", cancel), MessageHandler(filters.Regex("^Отмена$"), cancel)],
    )
    conv_crm = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^Изменить CRM$"), edit_crm_start)],
        states={ STATE_CRM_EDIT: [ MessageHandler(filters.TEXT & ~filters.COMMAND, edit_crm_save) ] },
        fallbacks=[CommandHandler("cancel", cancel), MessageHandler(filters.Regex("^Отмена$"), cancel)],
    )

    # Регистрация хендлеров
    app.add_handler(CommandHandler("start", start_menu))

    app.add_handler(conv_ticket)
    app.add_handler(conv_reply)
    app.add_handler(conv_broadcast)
    app.add_handler(conv_archive)
    app.add_handler(conv_stats)
    app.add_handler(conv_crm)

    # Пользовательские команды
    app.add_handler(MessageHandler(filters.Regex("^Мои запросы$"), my_requests))

    # Справка и CRM
    app.add_handler(MessageHandler(filters.Regex("^Справка$"), help_menu))
    app.add_handler(MessageHandler(filters.Regex("^Правила телефонии$"), rules_handler))
    app.add_handler(MessageHandler(filters.Regex("^Ссылки для работы$"), links_handler))
    app.add_handler(MessageHandler(filters.Regex("^Спич$"), speech_handler))
    app.add_handler(MessageHandler(filters.Regex("^CRM$"), crm_handler))
    app.add_handler(MessageHandler(filters.Regex("^Назад$"), back_to_main))

    # Админские простые кнопки
    app.add_handler(MessageHandler(filters.Regex("^Все запросы$"), all_requests_cmd))
    app.add_handler(MessageHandler(filters.Regex("^Очистить все запросы$"), clear_requests_admin))

    # CallbackQueryHandlers
    app.add_handler(CallbackQueryHandler(show_request, pattern=r"^show:\d+$"))
    app.add_handler(CallbackQueryHandler(cancel_request_callback, pattern=r"^cancel_req:\d+$"))
    app.add_handler(CallbackQueryHandler(status_callback, pattern=r"^status:\d+:"))

    app.run_polling()

if __name__ == "__main__":
    main()
