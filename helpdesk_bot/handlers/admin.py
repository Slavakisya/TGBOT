from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

from .. import db
from ..daily import refresh_daily_jobs
from ..utils import (
    ADMIN_IDS,
    ADMIN_MAIN_MENU,
    ADMIN_TICKETS_MENU,
    ADMIN_ANALYTICS_MENU,
    ADMIN_SETTINGS_MENU,
    ADMIN_DAILY_MESSAGE_MENU,
    ADMIN_PREDICTIONS_MENU,
    DAILY_MESSAGE_SELECTED_MENU,
    DAILY_MESSAGE_EDIT_KEYBOARD,
    DAILY_MESSAGE_FORMAT_MENU,
    PREDICTION_SELECTED_MENU,
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
    STATE_DAILY_MESSAGE_MENU,
    STATE_DAILY_MESSAGE_EDIT,
    STATE_DAILY_MESSAGE_FORMAT,
)


DAILY_STATE_KEY = "daily_message_state"
DAILY_STATE_MENU = "menu"
DAILY_STATE_EDIT = "edit"
DAILY_STATE_FORMAT = "format"
DAILY_STATE_SELECT = "select"
DAILY_STATE_SELECTED = "selected"
DAILY_STATE_EDIT_TIME = "edit_time"
DAILY_STATE_ADD_TIME = "add_time"
DAILY_STATE_ADD_TEXT = "add_text"

DAILY_SELECTED_KEY = "daily_message_selected_id"
DAILY_NEW_TIME_KEY = "daily_message_new_time"
DAILY_SKIP_KEY = "daily_message_skip_update"


PREDICTION_STATE_KEY = "prediction_state"
PREDICTION_STATE_MENU = "pred_menu"
PREDICTION_STATE_ADD = "pred_add"
PREDICTION_STATE_SELECT = "pred_select"
PREDICTION_STATE_SELECTED = "pred_selected"
PREDICTION_STATE_EDIT = "pred_edit"

PREDICTION_SELECTED_KEY = "prediction_selected_id"


def _normalize_button_text(value: str | None) -> str:
    if not value:
        return ""
    cleaned = value.replace("\uFE0F", "").strip()
    if cleaned.startswith("⬅") and not cleaned.startswith("⬅ "):
        cleaned = "⬅ " + cleaned[1:].lstrip()
    return " ".join(cleaned.split())


_BACK_BUTTON_CANONICAL = _normalize_button_text(ADMIN_BACK_BUTTON)

# Allow matching keyboards that omit the emoji variation selector or the space
# between the arrow icon and the label.
BACK_BUTTON_PATTERN = rf"^⬅\ufe0f?\s*{_BACK_BUTTON_CANONICAL.split(' ', 1)[-1]}$"


_ADMIN_ESCAPE_BUTTONS = {
    _normalize_button_text(value)
    for value in [
        "Заявки",
        "Аналитика",
        "Настройки",
        "Все запросы",
        "Архив запросов",
        "Очистить все запросы",
        "Статистика",
        "Благодарности",
        "Изменить CRM",
        "Изменить спич",
    ]
}


def _is_back_button(value: str | None) -> bool:
    normalized = _normalize_button_text(value)
    return normalized in {_BACK_BUTTON_CANONICAL, "Назад"}


def _set_daily_state(ctx: ContextTypes.DEFAULT_TYPE, value: str | None) -> None:
    if value is None:
        ctx.user_data.pop(DAILY_STATE_KEY, None)
    else:
        ctx.user_data[DAILY_STATE_KEY] = value


def _get_daily_state(ctx: ContextTypes.DEFAULT_TYPE) -> str | None:
    return ctx.user_data.get(DAILY_STATE_KEY)


def _set_selected_message(ctx: ContextTypes.DEFAULT_TYPE, message_id: int | None) -> None:
    if message_id is None:
        ctx.user_data.pop(DAILY_SELECTED_KEY, None)
    else:
        ctx.user_data[DAILY_SELECTED_KEY] = message_id


def _get_selected_message(ctx: ContextTypes.DEFAULT_TYPE) -> int | None:
    return ctx.user_data.get(DAILY_SELECTED_KEY)


def _set_new_message_time(ctx: ContextTypes.DEFAULT_TYPE, value: str | None) -> None:
    if value is None:
        ctx.user_data.pop(DAILY_NEW_TIME_KEY, None)
    else:
        ctx.user_data[DAILY_NEW_TIME_KEY] = value


def _reset_daily_workflow(ctx: ContextTypes.DEFAULT_TYPE) -> None:
    _set_daily_state(ctx, None)
    _set_selected_message(ctx, None)
    _set_new_message_time(ctx, None)
    ctx.user_data.pop(DAILY_SKIP_KEY, None)


def _set_prediction_state(ctx: ContextTypes.DEFAULT_TYPE, value: str | None) -> None:
    if value is None:
        ctx.user_data.pop(PREDICTION_STATE_KEY, None)
    else:
        ctx.user_data[PREDICTION_STATE_KEY] = value


def _get_prediction_state(ctx: ContextTypes.DEFAULT_TYPE) -> str | None:
    return ctx.user_data.get(PREDICTION_STATE_KEY)


def _set_selected_prediction(ctx: ContextTypes.DEFAULT_TYPE, prediction_id: int | None) -> None:
    if prediction_id is None:
        ctx.user_data.pop(PREDICTION_SELECTED_KEY, None)
    else:
        ctx.user_data[PREDICTION_SELECTED_KEY] = prediction_id


def _get_selected_prediction(ctx: ContextTypes.DEFAULT_TYPE) -> int | None:
    return ctx.user_data.get(PREDICTION_SELECTED_KEY)


def _reset_prediction_workflow(ctx: ContextTypes.DEFAULT_TYPE) -> None:
    _set_prediction_state(ctx, None)
    _set_selected_prediction(ctx, None)


def _get_new_message_time(ctx: ContextTypes.DEFAULT_TYPE) -> str | None:
    return ctx.user_data.get(DAILY_NEW_TIME_KEY)


def _mark_skip_update(ctx: ContextTypes.DEFAULT_TYPE, update: Update) -> None:
    update_id = getattr(update, "update_id", None)
    if update_id is not None:
        ctx.user_data[DAILY_SKIP_KEY] = update_id


def _should_skip_update(ctx: ContextTypes.DEFAULT_TYPE, update: Update) -> bool:
    update_id = getattr(update, "update_id", None)
    if update_id is not None and ctx.user_data.get(DAILY_SKIP_KEY) == update_id:
        ctx.user_data.pop(DAILY_SKIP_KEY, None)
        return True
    return False


def _is_valid_time(value: str) -> bool:
    try:
        hours_str, minutes_str = value.split(":", 1)
        hours = int(hours_str)
        minutes = int(minutes_str)
        return 0 <= hours < 24 and 0 <= minutes < 60
    except Exception:
        return False


async def _refresh_jobs_from_ctx(ctx: ContextTypes.DEFAULT_TYPE) -> None:
    app = getattr(ctx, "application", None)
    job_queue = None
    if app is not None:
        job_queue = getattr(app, "job_queue", None)
    elif hasattr(ctx, "job_queue"):
        job_queue = getattr(ctx, "job_queue")
    if job_queue:
        await refresh_daily_jobs(job_queue)


async def _send_predictions_menu(update: Update) -> None:
    predictions = await db.list_predictions()
    lines = ["Раздел «Предсказания».", f"Всего предсказаний: {len(predictions)}."]
    if predictions:
        lines.append("")
        lines.append("Последние записи:")
        for entry in predictions[:5]:
            preview = entry["text"].strip().splitlines()[0] if entry["text"].strip() else "— пусто —"
            if len(preview) > 100:
                preview = preview[:97] + "…"
            lines.append(f"{entry['id']}. {preview}")
        if len(predictions) > 5:
            lines.append("…")
    lines.append("")
    lines.append("Выберите действие:")
    await update.message.reply_text(
        "\n".join(lines),
        reply_markup=ReplyKeyboardMarkup(ADMIN_PREDICTIONS_MENU, resize_keyboard=True),
    )


async def _send_prediction_selected_menu(update: Update, prediction: dict) -> None:
    text = prediction["text"].strip() or "— пусто —"
    lines = [f"Предсказание #{prediction['id']}:", text]
    await update.message.reply_text(
        "\n\n".join(lines),
        reply_markup=ReplyKeyboardMarkup(
            PREDICTION_SELECTED_MENU, resize_keyboard=True
        ),
    )


async def predictions_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update):
        return
    _reset_prediction_workflow(ctx)
    _set_prediction_state(ctx, PREDICTION_STATE_MENU)
    await _send_predictions_menu(update)


async def predictions_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update):
        return

    state = _get_prediction_state(ctx)
    if state is None:
        return

    raw_choice = update.message.text or ""
    choice = raw_choice.strip()
    normalized_choice = _normalize_button_text(choice)

    if normalized_choice in _ADMIN_ESCAPE_BUTTONS:
        _reset_prediction_workflow(ctx)
        return

    if state in {PREDICTION_STATE_ADD, PREDICTION_STATE_EDIT}:
        return

    if state == PREDICTION_STATE_MENU:
        if _is_back_button(choice):
            _reset_prediction_workflow(ctx)
            await show_settings_menu(update, ctx)
            return

        if choice == "Добавить предсказание":
            _set_prediction_state(ctx, PREDICTION_STATE_ADD)
            await update.message.reply_text(
                "Отправьте текст нового предсказания.",
                reply_markup=CANCEL_KEYBOARD,
            )
            return

        if choice == "Настроить предсказание":
            predictions = await db.list_predictions()
            if not predictions:
                await update.message.reply_text(
                    "Список предсказаний пуст. Сначала добавьте предсказание.",
                    reply_markup=ReplyKeyboardMarkup(
                        ADMIN_PREDICTIONS_MENU, resize_keyboard=True
                    ),
                )
                return
            _set_prediction_state(ctx, PREDICTION_STATE_SELECT)
            lines = ["Доступные предсказания:"]
            for entry in predictions:
                preview = entry["text"].strip().splitlines()[0] if entry["text"].strip() else "— пусто —"
                if len(preview) > 100:
                    preview = preview[:97] + "…"
                lines.append(f"{entry['id']}. {preview}")
            lines.append("")
            lines.append("Отправьте ID предсказания для настройки или «Отмена».")
            await update.message.reply_text(
                "\n".join(lines),
                reply_markup=CANCEL_KEYBOARD,
            )
            return

        await update.message.reply_text(
            "Пожалуйста, используйте кнопки меню.",
            reply_markup=ReplyKeyboardMarkup(
                ADMIN_PREDICTIONS_MENU, resize_keyboard=True
            ),
        )
        return

    if state == PREDICTION_STATE_SELECT:
        if choice.lower() == "отмена" or _is_back_button(choice):
            _set_prediction_state(ctx, PREDICTION_STATE_MENU)
            await _send_predictions_menu(update)
            return
        if not choice.isdigit():
            await update.message.reply_text(
                "Укажите числовой ID предсказания или «Отмена».",
                reply_markup=CANCEL_KEYBOARD,
            )
            return
        prediction = await db.get_prediction(int(choice))
        if not prediction:
            await update.message.reply_text(
                "Предсказание с таким ID не найдено. Попробуйте снова.",
                reply_markup=CANCEL_KEYBOARD,
            )
            return
        _set_selected_prediction(ctx, prediction["id"])
        _set_prediction_state(ctx, PREDICTION_STATE_SELECTED)
        await _send_prediction_selected_menu(update, prediction)
        return

    if state == PREDICTION_STATE_SELECTED:
        prediction_id = _get_selected_prediction(ctx)
        if not prediction_id:
            _set_prediction_state(ctx, PREDICTION_STATE_MENU)
            await _send_predictions_menu(update)
            return

        if _is_back_button(choice):
            _set_selected_prediction(ctx, None)
            _set_prediction_state(ctx, PREDICTION_STATE_MENU)
            await _send_predictions_menu(update)
            return

        if choice == "Изменить текст":
            _set_prediction_state(ctx, PREDICTION_STATE_EDIT)
            await update.message.reply_text(
                "Отправьте новый текст предсказания.",
                reply_markup=CANCEL_KEYBOARD,
            )
            return

        if choice == "Удалить предсказание":
            await db.delete_prediction(prediction_id)
            await update.message.reply_text("✅ Предсказание удалено.")
            _set_selected_prediction(ctx, None)
            _set_prediction_state(ctx, PREDICTION_STATE_MENU)
            await _send_predictions_menu(update)
            return

        await update.message.reply_text(
            "Пожалуйста, используйте кнопки меню.",
            reply_markup=ReplyKeyboardMarkup(
                PREDICTION_SELECTED_MENU, resize_keyboard=True
            ),
        )
        return


async def predictions_save(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update):
        return

    state = _get_prediction_state(ctx)
    if state not in {PREDICTION_STATE_ADD, PREDICTION_STATE_EDIT}:
        return

    raw_text = update.message.text or ""
    text = raw_text.strip()

    if text.lower() == "отмена":
        if state == PREDICTION_STATE_ADD:
            _set_prediction_state(ctx, PREDICTION_STATE_MENU)
            await _send_predictions_menu(update)
        else:
            _set_prediction_state(ctx, PREDICTION_STATE_SELECTED)
            prediction_id = _get_selected_prediction(ctx)
            if prediction_id:
                prediction = await db.get_prediction(prediction_id)
                if prediction:
                    await _send_prediction_selected_menu(update, prediction)
                    return
            _set_prediction_state(ctx, PREDICTION_STATE_MENU)
            await _send_predictions_menu(update)
        return

    if state == PREDICTION_STATE_ADD:
        if not text:
            await update.message.reply_text(
                "Текст предсказания не может быть пустым.",
                reply_markup=CANCEL_KEYBOARD,
            )
            return
        await db.add_prediction(text)
        await update.message.reply_text("✅ Предсказание добавлено.")
        _set_prediction_state(ctx, PREDICTION_STATE_MENU)
        await _send_predictions_menu(update)
        return

    if state == PREDICTION_STATE_EDIT:
        prediction_id = _get_selected_prediction(ctx)
        if not prediction_id:
            _set_prediction_state(ctx, PREDICTION_STATE_MENU)
            await _send_predictions_menu(update)
            return
        if not text:
            await update.message.reply_text(
                "Текст предсказания не может быть пустым.",
                reply_markup=CANCEL_KEYBOARD,
            )
            return
        await db.update_prediction(prediction_id, text)
        await update.message.reply_text("✅ Предсказание обновлено.")
        _set_prediction_state(ctx, PREDICTION_STATE_SELECTED)
        prediction = await db.get_prediction(prediction_id)
        if prediction:
            await _send_prediction_selected_menu(update, prediction)
        else:
            _set_selected_prediction(ctx, None)
            _set_prediction_state(ctx, PREDICTION_STATE_MENU)
            await _send_predictions_menu(update)

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
    _reset_daily_workflow(ctx)
    _reset_prediction_workflow(ctx)
    await update.message.reply_text(
        "Раздел «Настройки». Выберите действие:",
        reply_markup=ReplyKeyboardMarkup(ADMIN_SETTINGS_MENU, resize_keyboard=True),
    )


async def back_to_main(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update):
        return
    _reset_daily_workflow(ctx)
    _reset_prediction_workflow(ctx)
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
    messages = await db.list_daily_messages()
    chat_id = await db.get_setting("daily_message_chat_id") or ""

    lines = ["Ежедневные сообщения:"]
    if not messages:
        lines.append("— сообщений нет —")
    else:
        for entry in messages:
            preview = entry["text"].strip().splitlines()[0] if entry["text"].strip() else "— пусто —"
            lines.append(f"{entry['id']}. {entry['send_time']} — {preview}")

    lines.append("")
    if chat_id:
        lines.append(f"Чат для отправки: {chat_id}")
    else:
        lines.append(
            "Чат для отправки не привязан. Добавьте бота администратором в нужную группу, чтобы закрепить её."
        )
    lines.append("")
    lines.append("Выберите действие:")

    return {
        "messages": messages,
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


async def _send_selected_menu(update: Update, message: dict) -> None:
    parse_mode_label = {
        "": "обычный текст",
        "Markdown": "Markdown",
        "HTML": "HTML",
    }.get(message["parse_mode"], message["parse_mode"])

    preview_label = "выключен" if message["disable_preview"] else "включён"

    lines = [
        f"Сообщение #{message['id']}",
        f"Время отправки: {message['send_time']}",
        f"Форматирование: {parse_mode_label}",
        f"Предпросмотр ссылок: {preview_label}",
        "",
    ]
    lines.append(message["text"] if message["text"].strip() else "— текст не задан —")
    lines.append("")
    lines.append("Выберите действие:")

    await update.message.reply_text(
        "\n".join(lines),
        reply_markup=ReplyKeyboardMarkup(DAILY_MESSAGE_SELECTED_MENU, resize_keyboard=True),
    )


async def daily_message_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update):
        return
    _reset_daily_workflow(ctx)
    _set_daily_state(ctx, DAILY_STATE_MENU)
    await _send_daily_menu(update)


async def daily_message_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update):
        return

    state = _get_daily_state(ctx)
    if state is None:
        return

    raw_choice = update.message.text or ""
    choice = raw_choice.strip()
    normalized_choice = _normalize_button_text(choice)

    if normalized_choice in _ADMIN_ESCAPE_BUTTONS:
        _reset_daily_workflow(ctx)
        return

    if state in {
        DAILY_STATE_EDIT,
        DAILY_STATE_ADD_TIME,
        DAILY_STATE_ADD_TEXT,
        DAILY_STATE_EDIT_TIME,
        DAILY_STATE_FORMAT,
    }:
        return

    if state == DAILY_STATE_MENU:
        if _is_back_button(choice):
            _set_daily_state(ctx, None)
            await show_settings_menu(update, ctx)
            return

        if choice == "Добавить сообщение":
            _set_daily_state(ctx, DAILY_STATE_ADD_TIME)
            _mark_skip_update(ctx, update)
            await update.message.reply_text(
                "Введите время отправки в формате ЧЧ:ММ (по Киеву).",
                reply_markup=CANCEL_KEYBOARD,
            )
            return

        if choice == "Настроить сообщение":
            overview = await _daily_overview()
            if not overview["messages"]:
                await update.message.reply_text(
                    "Список сообщений пуст. Сначала добавьте новое сообщение.",
                    reply_markup=ReplyKeyboardMarkup(
                        ADMIN_DAILY_MESSAGE_MENU, resize_keyboard=True
                    ),
                )
                return
            _set_daily_state(ctx, DAILY_STATE_SELECT)
            lines = ["Доступные сообщения:"]
            for entry in overview["messages"]:
                preview = entry["text"].strip().splitlines()[0] if entry["text"].strip() else "— пусто —"
                lines.append(f"{entry['id']}. {entry['send_time']} — {preview}")
            lines.append("")
            lines.append("Отправьте ID сообщения для настройки или «Отмена».")
            await update.message.reply_text(
                "\n".join(lines),
                reply_markup=CANCEL_KEYBOARD,
            )
            return

        await update.message.reply_text(
            "Пожалуйста, используйте кнопки меню.",
            reply_markup=ReplyKeyboardMarkup(ADMIN_DAILY_MESSAGE_MENU, resize_keyboard=True),
        )
        return

    if state == DAILY_STATE_SELECT:
        if choice.lower() == "отмена" or _is_back_button(choice):
            _set_daily_state(ctx, DAILY_STATE_MENU)
            await _send_daily_menu(update)
            return
        if not choice.isdigit():
            await update.message.reply_text(
                "Укажите числовой ID сообщения или «Отмена».",
                reply_markup=CANCEL_KEYBOARD,
            )
            return
        message = await db.get_daily_message(int(choice))
        if not message:
            await update.message.reply_text(
                "Сообщение с таким ID не найдено. Попробуйте снова.",
                reply_markup=CANCEL_KEYBOARD,
            )
            return
        _set_selected_message(ctx, message["id"])
        _set_daily_state(ctx, DAILY_STATE_SELECTED)
        await _send_selected_menu(update, message)
        return

    if state == DAILY_STATE_SELECTED:
        message_id = _get_selected_message(ctx)
        if not message_id:
            _set_daily_state(ctx, DAILY_STATE_MENU)
            await _send_daily_menu(update)
            return

        if _is_back_button(choice):
            _set_selected_message(ctx, None)
            _set_daily_state(ctx, DAILY_STATE_MENU)
            await _send_daily_menu(update)
            return

        if choice == "Изменить текст":
            _set_daily_state(ctx, DAILY_STATE_EDIT)
            _mark_skip_update(ctx, update)
            await update.message.reply_text(
                "Отправьте новый текст сообщения. Для очистки используйте «Пусто».",
                reply_markup=ReplyKeyboardMarkup(
                    DAILY_MESSAGE_EDIT_KEYBOARD, resize_keyboard=True
                ),
            )
            return

        if choice == "Изменить время":
            _set_daily_state(ctx, DAILY_STATE_EDIT_TIME)
            _mark_skip_update(ctx, update)
            await update.message.reply_text(
                "Введите новое время в формате ЧЧ:ММ (по Киеву).",
                reply_markup=CANCEL_KEYBOARD,
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
            message = await db.get_daily_message(message_id)
            if not message:
                await update.message.reply_text(
                    "Сообщение не найдено.",
                    reply_markup=ReplyKeyboardMarkup(
                        ADMIN_DAILY_MESSAGE_MENU, resize_keyboard=True
                    ),
                )
                _set_selected_message(ctx, None)
                _set_daily_state(ctx, DAILY_STATE_MENU)
                await _send_daily_menu(update)
                return
            new_value = not message["disable_preview"]
            await db.update_daily_message(message_id, disable_preview=new_value)
            status = "включён" if not new_value else "выключен"
            await update.message.reply_text(f"Предпросмотр ссылок {status}.")
            updated = await db.get_daily_message(message_id)
            if updated:
                await _send_selected_menu(update, updated)
            return

        if choice == "Предпросмотр":
            message = await db.get_daily_message(message_id)
            if not message or not message["text"].strip():
                await update.message.reply_text(
                    "Текст сообщения не задан.",
                    reply_markup=ReplyKeyboardMarkup(
                        DAILY_MESSAGE_SELECTED_MENU, resize_keyboard=True
                    ),
                )
                return
            try:
                await update.message.reply_text(
                    message["text"],
                    parse_mode=message["parse_mode"] or None,
                    disable_web_page_preview=message["disable_preview"],
                )
            except Exception as exc:  # pragma: no cover
                log.warning(
                    "Не удалось показать предпросмотр ежедневного сообщения #%s: %s",
                    message_id,
                    exc,
                )
                await update.message.reply_text(
                    "Не удалось показать предпросмотр.",
                    reply_markup=ReplyKeyboardMarkup(
                        DAILY_MESSAGE_SELECTED_MENU, resize_keyboard=True
                    ),
                )
            return

        if choice == "Удалить сообщение":
            await db.delete_daily_message(message_id)
            await update.message.reply_text("Сообщение удалено.")
            _set_selected_message(ctx, None)
            _set_daily_state(ctx, DAILY_STATE_MENU)
            await _refresh_jobs_from_ctx(ctx)
            await _send_daily_menu(update)
            return

        await update.message.reply_text(
            "Пожалуйста, используйте кнопки меню.",
            reply_markup=ReplyKeyboardMarkup(
                DAILY_MESSAGE_SELECTED_MENU, resize_keyboard=True
            ),
        )


async def daily_message_save(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update):
        return

    state = _get_daily_state(ctx)
    if _should_skip_update(ctx, update):
        return
    if state not in {
        DAILY_STATE_EDIT,
        DAILY_STATE_ADD_TIME,
        DAILY_STATE_ADD_TEXT,
        DAILY_STATE_EDIT_TIME,
    }:
        return

    message_id = _get_selected_message(ctx)
    raw_text = update.message.text or ""
    choice = raw_text.strip()
    lowered = choice.lower()

    if state == DAILY_STATE_ADD_TIME:
        if lowered == "отмена":
            _set_new_message_time(ctx, None)
            _set_daily_state(ctx, DAILY_STATE_MENU)
            await _send_daily_menu(update)
            return
        if not _is_valid_time(choice):
            await update.message.reply_text(
                "Неверный формат времени. Укажите ЧЧ:ММ.",
                reply_markup=CANCEL_KEYBOARD,
            )
            return
        _set_new_message_time(ctx, choice)
        _set_daily_state(ctx, DAILY_STATE_ADD_TEXT)
        await update.message.reply_text(
            "Отправьте текст нового сообщения. Для пустого сообщения используйте «Пусто».",
            reply_markup=ReplyKeyboardMarkup(
                DAILY_MESSAGE_EDIT_KEYBOARD, resize_keyboard=True
            ),
        )
        return

    if state == DAILY_STATE_ADD_TEXT:
        if lowered == "отмена":
            _set_new_message_time(ctx, None)
            _set_daily_state(ctx, DAILY_STATE_MENU)
            await _send_daily_menu(update)
            return
        send_time = _get_new_message_time(ctx)
        if send_time is None:
            _set_daily_state(ctx, DAILY_STATE_MENU)
            await _send_daily_menu(update)
            return
        text_value = "" if lowered == "пусто" else raw_text
        new_id = await db.add_daily_message(text_value, send_time)
        await update.message.reply_text("✅ Сообщение добавлено.")
        _set_new_message_time(ctx, None)
        _set_selected_message(ctx, new_id)
        _set_daily_state(ctx, DAILY_STATE_SELECTED)
        await _refresh_jobs_from_ctx(ctx)
        message = await db.get_daily_message(new_id)
        if message:
            await _send_selected_menu(update, message)
        else:
            _set_daily_state(ctx, DAILY_STATE_MENU)
            await _send_daily_menu(update)
        return

    if state == DAILY_STATE_EDIT:
        if lowered == "отмена":
            _set_daily_state(ctx, DAILY_STATE_SELECTED if message_id else DAILY_STATE_MENU)
            if message_id:
                message = await db.get_daily_message(message_id)
                if message:
                    await _send_selected_menu(update, message)
                    return
            await _send_daily_menu(update)
            return

        if message_id is None:
            _set_daily_state(ctx, DAILY_STATE_MENU)
            await _send_daily_menu(update)
            return

        text_value = "" if lowered == "пусто" else raw_text
        await db.update_daily_message(message_id, text=text_value)
        await update.message.reply_text(
            "✅ Текст сообщения обновлён." if text_value else "✅ Сообщение очищено."
        )
        _set_daily_state(ctx, DAILY_STATE_SELECTED)
        message = await db.get_daily_message(message_id)
        if message:
            await _send_selected_menu(update, message)
        else:
            _set_selected_message(ctx, None)
            _set_daily_state(ctx, DAILY_STATE_MENU)
            await _send_daily_menu(update)
        return

    if state == DAILY_STATE_EDIT_TIME:
        if lowered == "отмена":
            _set_daily_state(ctx, DAILY_STATE_SELECTED if message_id else DAILY_STATE_MENU)
            if message_id:
                message = await db.get_daily_message(message_id)
                if message:
                    await _send_selected_menu(update, message)
                    return
            await _send_daily_menu(update)
            return
        if not _is_valid_time(choice):
            await update.message.reply_text(
                "Неверный формат времени. Укажите ЧЧ:ММ.",
                reply_markup=CANCEL_KEYBOARD,
            )
            return
        if message_id is None:
            _set_daily_state(ctx, DAILY_STATE_MENU)
            await _send_daily_menu(update)
            return
        await db.update_daily_message(message_id, send_time=choice)
        await update.message.reply_text(f"Время отправки обновлено на {choice}.")
        _set_daily_state(ctx, DAILY_STATE_SELECTED)
        await _refresh_jobs_from_ctx(ctx)
        message = await db.get_daily_message(message_id)
        if message:
            await _send_selected_menu(update, message)
        else:
            _set_selected_message(ctx, None)
            _set_daily_state(ctx, DAILY_STATE_MENU)
            await _send_daily_menu(update)


async def daily_message_set_format(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update):
        return

    if _get_daily_state(ctx) != DAILY_STATE_FORMAT:
        return

    choice = (update.message.text or "").strip()
    lowered = choice.lower()

    if lowered == "отмена" or _is_back_button(choice):
        message_id = _get_selected_message(ctx)
        await update.message.reply_text("Настройка форматирования отменена.")
        _set_daily_state(ctx, DAILY_STATE_SELECTED if message_id else DAILY_STATE_MENU)
        if message_id:
            message = await db.get_daily_message(message_id)
            if message:
                await _send_selected_menu(update, message)
                return
            _set_selected_message(ctx, None)
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

    message_id = _get_selected_message(ctx)
    if message_id is None:
        _set_daily_state(ctx, DAILY_STATE_MENU)
        await _send_daily_menu(update)
        return

    await db.update_daily_message(message_id, parse_mode=modes[lowered])
    label = "обычный текст" if modes[lowered] == "" else modes[lowered]
    await update.message.reply_text(f"Форматирование изменено на: {label}.")
    _set_daily_state(ctx, DAILY_STATE_SELECTED)
    message = await db.get_daily_message(message_id)
    if message:
        await _send_selected_menu(update, message)
    else:
        _set_selected_message(ctx, None)
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
            _reset_daily_workflow(ctx)
        ctx.user_data.pop("reply_ticket", None)
    await update.message.reply_text(
        "❌ Отменено.",
        reply_markup=ReplyKeyboardMarkup(menu, resize_keyboard=True),
    )
    return ConversationHandler.END
