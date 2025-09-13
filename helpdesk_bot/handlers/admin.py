from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

from .. import db
from ..utils import (
    ADMIN_IDS,
    ADMIN_MAIN_MENU,
    STATUS_OPTIONS,
    ALL_ADMINS,
    CANCEL_KEYBOARD,
    USER_MAIN_MENU,
    format_kyiv_time,
    log,
    STATE_REPLY,
    STATE_BROADCAST,
    STATE_ARCHIVE_DATE,
    STATE_STATS_DATE,
    STATE_CRM_EDIT,
    STATE_SPEECH_EDIT,
)


async def init_reply(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query
    await q.answer()
    rid = int(q.data.split(":")[1])
    ctx.user_data["reply_ticket"] = rid
    await q.message.reply_text(
        f"Введите ответ для запроса #{rid}:", reply_markup=CANCEL_KEYBOARD
    )
    return STATE_REPLY


async def handle_reply(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    txt = update.message.text.strip()
    if txt == "Отмена":
        return await cancel(update, ctx)
    rid = ctx.user_data.get("reply_ticket")
    tkt = await db.get_ticket(rid)
    if tkt:
        await ctx.bot.send_message(
            tkt[5], f"💬 Ответ на запрос #{rid}:\n{txt}"
        )
        await update.message.reply_text(
            "Ответ отправлен.",
            reply_markup=ReplyKeyboardMarkup(ADMIN_MAIN_MENU, resize_keyboard=True),
        )
    else:
        await update.message.reply_text(
            "Запрос не найден.",
            reply_markup=ReplyKeyboardMarkup(ADMIN_MAIN_MENU, resize_keyboard=True),
        )
    return ConversationHandler.END


async def init_broadcast(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "Введите текст рассылки:", reply_markup=CANCEL_KEYBOARD
    )
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
        reply_markup=ReplyKeyboardMarkup(ADMIN_MAIN_MENU, resize_keyboard=True),
    )
    return ConversationHandler.END


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
        btns_s = [
            InlineKeyboardButton(s, callback_data=f"status:{rid}:{s}")
            for s in STATUS_OPTIONS
            if s != "отменено"
        ]
        btn_r = InlineKeyboardButton("Ответить", callback_data=f"reply:{rid}")
        await ctx.bot.send_message(
            update.effective_chat.id,
            f"#{rid} [{st}]\n{rowc}: {prob}\nОписание: {descr}\nОт: {uname}, {created}",
            reply_markup=InlineKeyboardMarkup([btns_s, [btn_r]]),
        )


async def init_archive(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "Введите дату (ГГГГ-ММ-ДД):", reply_markup=CANCEL_KEYBOARD
    )
    return STATE_ARCHIVE_DATE


async def archive_date_invalid(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "Неверный формат. Введите ГГГГ-ММ-ДД:", reply_markup=CANCEL_KEYBOARD
    )
    return STATE_ARCHIVE_DATE


async def archive_by_date_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    d = update.message.text.strip()
    all_r = await db.list_tickets()
    arch = [r for r in all_r if r[7].startswith(d) and r[6] in ("готово", "отменено")]
    if not arch:
        await update.message.reply_text(
            f"Нет запросов за {d}.",
            reply_markup=ReplyKeyboardMarkup(ADMIN_MAIN_MENU, resize_keyboard=True),
        )
    else:
        for r in arch:
            rid, rowc, prob, descr, uname, uid, st, cts = r
            c = format_kyiv_time(cts)
            await update.message.reply_text(
                f"#{rid} [{st}]\n{rowc}: {prob}\nОписание: {descr}\nОт: {uname}, {c}"
            )
        await update.message.reply_text(
            "Меню администратора:",
            reply_markup=ReplyKeyboardMarkup(ADMIN_MAIN_MENU, resize_keyboard=True),
        )
    return ConversationHandler.END


async def stats_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "Введите период статистики (YYYY-MM-DD — YYYY-MM-DD):",
        reply_markup=CANCEL_KEYBOARD,
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
            reply_markup=CANCEL_KEYBOARD,
        )
        return STATE_STATS_DATE
    start_str, end_str = parts
    by_status = await db.count_by_status(start_str, end_str)
    by_problem = await db.count_by_problem(start_str, end_str)
    lines = [f"📊 Стата с {start_str} по {end_str}:", "\nПо статусам:"]
    for st, cnt in by_status.items():
        lines.append(f"  • {st}: {cnt}")
    lines.append("\nПо типам проблем:")
    for pr, cnt in by_problem.items():
        lines.append(f"  • {pr}: {cnt}")
    await update.message.reply_text(
        "\n".join(lines),
        reply_markup=ReplyKeyboardMarkup(ADMIN_MAIN_MENU, resize_keyboard=True),
    )
    return ConversationHandler.END


async def edit_crm_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    if update.effective_user.id not in ADMIN_IDS:
        return ConversationHandler.END
    await update.message.reply_text(
        "Введите весь текст CRM:", reply_markup=CANCEL_KEYBOARD
    )
    return STATE_CRM_EDIT


async def edit_crm_save(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    txt = update.message.text
    if txt == "Отмена":
        return await cancel(update, ctx)
    await db.set_setting("crm_text", txt)
    await update.message.reply_text(
        "✅ CRM сохранена.",
        reply_markup=ReplyKeyboardMarkup(ADMIN_MAIN_MENU, resize_keyboard=True),
    )
    return ConversationHandler.END


async def edit_speech_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    if update.effective_user.id not in ADMIN_IDS:
        return ConversationHandler.END
    await update.message.reply_text(
        "Введите весь текст спича:", reply_markup=CANCEL_KEYBOARD
    )
    return STATE_SPEECH_EDIT


async def edit_speech_save(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    txt = update.message.text
    if txt == "Отмена":
        return await cancel(update, ctx)
    await db.set_setting("speech_text", txt)
    await update.message.reply_text(
        "✅ Спич сохранён.",
        reply_markup=ReplyKeyboardMarkup(ADMIN_MAIN_MENU, resize_keyboard=True),
    )
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
        btns_s = [
            InlineKeyboardButton(s, callback_data=f"status:{rid}:{s}")
            for s in STATUS_OPTIONS
            if s != "отменено"
        ]
        btn_r = InlineKeyboardButton("Ответить", callback_data=f"reply:{rid}")
        await q.edit_message_text(
            f"#{rid} — статус: «{new_st}»",
            reply_markup=InlineKeyboardMarkup([btns_s, [btn_r]]),
        )

    tkt = await db.get_ticket(rid)
    if not tkt:
        return

    user_id = tkt[5]

    for aid in ALL_ADMINS:
        try:
            await ctx.bot.send_message(
                aid, f"🔔 Статус запроса #{rid} обновлён на «{new_st}»"
            )
        except Exception as e:
            log.warning(
                "Не удалось уведомить админа %s об обновлении статуса #%s: %s",
                aid,
                rid,
                e,
            )

    try:
        await ctx.bot.send_message(
            user_id, f"🔔 Статус вашего запроса #{rid} обновлён: «{new_st}»"
        )
    except Exception as e:
        log.exception(
            "Не удалось уведомить пользователя %s о статусе #%s", user_id, rid, exc_info=e
        )
        for aid in ALL_ADMINS:
            try:
                await ctx.bot.send_message(
                    aid,
                    f"⚠️ Не удалось уведомить пользователя {user_id} об обновлении статуса запроса #{rid}",
                )
            except Exception as e2:
                log.warning(
                    "Не удалось уведомить админа %s о сбое: %s", aid, e2
                )

    if new_st == "готово":
        fb_btn = InlineKeyboardButton(
            "Проблема не решена", callback_data=f"feedback:{rid}"
        )
        th_btn = InlineKeyboardButton(
            "спасибо любимый айтишник <3", callback_data=f"thanks:{rid}"
        )
        await ctx.bot.send_message(
            user_id,
            "Если проблема не решена или хотите поблагодарить, нажмите:",
            reply_markup=InlineKeyboardMarkup([[fb_btn, th_btn]]),
        )


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
            await ctx.bot.send_message(
                aid, f"🙏 Пользователь {q.from_user.full_name} поблагодарил за запрос #{rid}."
            )
        except Exception as e:
            log.warning("Не удалось отправить благодарность админу %s: %s", aid, e)
    await q.edit_message_text("Спасибо за благодарность! ❤")
    await ctx.bot.send_message(
        q.from_user.id,
        "Главное меню:",
        reply_markup=ReplyKeyboardMarkup(USER_MAIN_MENU, resize_keyboard=True),
    )


async def show_thanks_count(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    cnts = []
    for aid in ALL_ADMINS:
        v = await db.get_setting(f"thanks_{aid}") or "0"
        cnts.append(f"Admin {aid}: {v}")
    await update.message.reply_text(
        "Благодарности:\n" + "\n".join(cnts),
        reply_markup=ReplyKeyboardMarkup(ADMIN_MAIN_MENU, resize_keyboard=True),
    )


async def clear_requests_admin(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id not in ADMIN_IDS:
        return
    await db.clear_requests()
    await ctx.bot.send_message(
        update.effective_chat.id, "🔄 Все запросы удалены администратором."
    )


async def cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "❌ Отменено.",
        reply_markup=ReplyKeyboardMarkup(USER_MAIN_MENU, resize_keyboard=True),
    )
    return ConversationHandler.END
