from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

from .. import db
from ..utils import (
    ADMIN_IDS,
    ADMIN_MAIN_MENU,
    ADMIN_TICKETS_MENU,
    ADMIN_ANALYTICS_MENU,
    ADMIN_SETTINGS_MENU,
    ADMIN_DAILY_MESSAGE_MENU,
    DAILY_MESSAGE_EDIT_KEYBOARD,
    DAILY_MESSAGE_FORMAT_MENU,
    ADMIN_BACK_BUTTON,
    STATUS_OPTIONS,
    ALL_ADMINS,
    CANCEL_KEYBOARD,
    USER_MAIN_MENU,
    format_kyiv_time,
    log,
    STATE_ARCHIVE_DATE,
    STATE_STATS_DATE,
    STATE_CRM_EDIT,
    STATE_SPEECH_EDIT,
)


DAILY_STATE_KEY = "daily_message_state"
DAILY_STATE_MENU = "menu"
DAILY_STATE_EDIT = "edit"
DAILY_STATE_FORMAT = "format"


def _set_daily_state(ctx: ContextTypes.DEFAULT_TYPE, value: str | None) -> None:
    if value is None:
        ctx.user_data.pop(DAILY_STATE_KEY, None)
    else:
        ctx.user_data[DAILY_STATE_KEY] = value


def _get_daily_state(ctx: ContextTypes.DEFAULT_TYPE) -> str | None:
    return ctx.user_data.get(DAILY_STATE_KEY)


async def init_reply(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    rid = int(q.data.split(":")[1])
    ctx.user_data["reply_ticket"] = rid
    await q.message.reply_text(
        f"Введите ответ для запроса #{rid}:", reply_markup=CANCEL_KEYBOARD
    )


async def handle_reply(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    rid = ctx.user_data.get("reply_ticket")
    if not rid:
        return

    txt = (update.message.text or "").strip()
    if txt == "Отмена":
        ctx.user_data.pop("reply_ticket", None)
        await cancel(update, ctx)
        return

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
    ctx.user_data.pop("reply_ticket", None)


def _is_admin(update: Update) -> bool:
    user = update.effective_user
    return bool(user and user.id in ADMIN_IDS)


async def show_tickets_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update):
        return
    await update.message.reply_text(
        "Раздел «Заявки». Выберите действие:",
        reply_markup=ReplyKeyboardMarkup(ADMIN_TICKETS_MENU, resize_keyboard=True),
    )


async def show_analytics_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update):
        return
    await update.message.reply_text(
        "Раздел «Аналитика». Выберите действие:",
        reply_markup=ReplyKeyboardMarkup(ADMIN_ANALYTICS_MENU, resize_keyboard=True),
    )


async def show_settings_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update):
        return
    _set_daily_state(ctx, None)
    await update.message.reply_text(
        "Раздел «Настройки». Выберите действие:",
        reply_markup=ReplyKeyboardMarkup(ADMIN_SETTINGS_MENU, resize_keyboard=True),
    )


async def back_to_main(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update):
        return
    if _get_daily_state(ctx):
        _set_daily_state(ctx, None)
    await update.message.reply_text(
        "Меню администратора:",
        reply_markup=ReplyKeyboardMarkup(ADMIN_MAIN_MENU, resize_keyboard=True),
    )


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


async def _daily_overview() -> dict:
    text = await db.get_setting("daily_message_text") or ""
    parse_mode = await db.get_setting("daily_message_parse_mode") or ""
    disable_preview = (
        await db.get_setting("daily_message_disable_preview") or "0"
    ) == "1"
    chat_id = await db.get_setting("daily_message_chat_id") or ""

    parse_mode_label = {
        "": "обычный текст",
        "Markdown": "Markdown",
        "HTML": "HTML",
    }.get(parse_mode, parse_mode)
    preview_label = "выключен" if disable_preview else "включен"

    lines = ["Ежедневное сообщение (17:00 Europe/Kyiv):"]
    lines.append(text if text else "— текст не задан —")
    lines.append("")
    lines.append(f"Форматирование: {parse_mode_label}")
    lines.append(f"Предпросмотр ссылок: {preview_label}")
    if chat_id:
        lines.append(f"Чат для отправки: {chat_id}")
    else:
        lines.append(
            "Чат для отправки не привязан. Добавьте бота администратором в нужную группу, чтобы закрепить её."
        )
    lines.append("")
    lines.append("Выберите действие:")

    return {
        "text": text,
        "parse_mode": parse_mode,
        "disable_preview": disable_preview,
        "chat_id": chat_id,
        "summary": "\n".join(lines),
    }


async def _send_daily_menu(update: Update) -> dict:
    overview = await _daily_overview()
    await update.message.reply_text(
        overview["summary"],
        reply_markup=ReplyKeyboardMarkup(ADMIN_DAILY_MESSAGE_MENU, resize_keyboard=True),
    )
    return overview


async def daily_message_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update):
        return
    _set_daily_state(ctx, DAILY_STATE_MENU)
    await _send_daily_menu(update)


async def daily_message_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update):
        return

    if _get_daily_state(ctx) != DAILY_STATE_MENU:
        return

    choice = update.message.text.strip()

    if choice == ADMIN_BACK_BUTTON:
        _set_daily_state(ctx, None)
        await show_settings_menu(update, ctx)
        return

    if choice == "Изменить текст":
        _set_daily_state(ctx, DAILY_STATE_EDIT)
        await update.message.reply_text(
            "Отправьте новый текст сообщения. Для отключения отправьте «Пусто».",
            reply_markup=ReplyKeyboardMarkup(DAILY_MESSAGE_EDIT_KEYBOARD, resize_keyboard=True),
        )
        return

    if choice == "Предпросмотр":
        overview = await _daily_overview()
        if not overview["text"]:
            await update.message.reply_text(
                "Текст сообщения не задан.",
                reply_markup=ReplyKeyboardMarkup(
                    ADMIN_DAILY_MESSAGE_MENU, resize_keyboard=True
                ),
            )
            return
        try:
            await update.message.reply_text(
                overview["text"],
                parse_mode=overview["parse_mode"] or None,
                disable_web_page_preview=overview["disable_preview"],
            )
        except Exception as exc:  # pragma: no cover - Telegram errors are runtime only
            log.warning("Не удалось показать предпросмотр ежедневного сообщения: %s", exc)
            await update.message.reply_text(
                "Не удалось показать предпросмотр.",
                reply_markup=ReplyKeyboardMarkup(
                    ADMIN_DAILY_MESSAGE_MENU, resize_keyboard=True
                ),
            )
        return

    if choice == "Форматирование":
        _set_daily_state(ctx, DAILY_STATE_FORMAT)
        await update.message.reply_text(
            "Выберите режим форматирования:",
            reply_markup=ReplyKeyboardMarkup(
                DAILY_MESSAGE_FORMAT_MENU, resize_keyboard=True
            ),
        )
        return

    if choice == "Переключить предпросмотр":
        current = await db.get_setting("daily_message_disable_preview") or "0"
        new_value = "0" if current == "1" else "1"
        await db.set_setting("daily_message_disable_preview", new_value)
        status = "включён" if new_value == "0" else "выключен"
        await update.message.reply_text(f"Предпросмотр ссылок {status}.")
        await _send_daily_menu(update)
        return

    if choice == "Очистить сообщение":
        await db.set_setting("daily_message_text", "")
        await update.message.reply_text("Ежедневное сообщение очищено.")
        await _send_daily_menu(update)
        return

    await update.message.reply_text(
        "Пожалуйста, используйте кнопки меню.",
        reply_markup=ReplyKeyboardMarkup(ADMIN_DAILY_MESSAGE_MENU, resize_keyboard=True),
    )


async def daily_message_save(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update):
        return

    if _get_daily_state(ctx) != DAILY_STATE_EDIT:
        return

    raw_text = update.message.text or ""
    choice = raw_text.strip().lower()

    if choice == "отмена":
        await update.message.reply_text("Изменение отменено.")
        _set_daily_state(ctx, DAILY_STATE_MENU)
        await _send_daily_menu(update)
        return

    if choice == "пусто":
        await db.set_setting("daily_message_text", "")
        await update.message.reply_text("✅ Ежедневное сообщение отключено.")
        _set_daily_state(ctx, DAILY_STATE_MENU)
        await _send_daily_menu(update)
        return

    await db.set_setting("daily_message_text", raw_text)
    await update.message.reply_text("✅ Ежедневное сообщение обновлено.")
    _set_daily_state(ctx, DAILY_STATE_MENU)
    await _send_daily_menu(update)


async def daily_message_set_format(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update):
        return

    if _get_daily_state(ctx) != DAILY_STATE_FORMAT:
        return

    choice = (update.message.text or "").strip()
    lowered = choice.lower()

    if lowered == "отмена" or choice == ADMIN_BACK_BUTTON:
        await update.message.reply_text("Настройка форматирования отменена.")
        _set_daily_state(ctx, DAILY_STATE_MENU)
        await _send_daily_menu(update)
        return

    modes = {
        "обычный текст": "",
        "markdown": "Markdown",
        "html": "HTML",
    }

    if lowered not in modes:
        await update.message.reply_text(
            "Выберите один из доступных вариантов:",
            reply_markup=ReplyKeyboardMarkup(
                DAILY_MESSAGE_FORMAT_MENU, resize_keyboard=True
            ),
        )
        return

    await db.set_setting("daily_message_parse_mode", modes[lowered])
    label = "обычный текст" if modes[lowered] == "" else modes[lowered]
    await update.message.reply_text(f"Форматирование изменено на: {label}.")
    _set_daily_state(ctx, DAILY_STATE_MENU)
    await _send_daily_menu(update)


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
    menu = USER_MAIN_MENU
    if _is_admin(update):
        menu = ADMIN_MAIN_MENU
        if _get_daily_state(ctx):
            _set_daily_state(ctx, None)
        ctx.user_data.pop("reply_ticket", None)
    await update.message.reply_text(
        "❌ Отменено.",
        reply_markup=ReplyKeyboardMarkup(menu, resize_keyboard=True),
    )
    return ConversationHandler.END
