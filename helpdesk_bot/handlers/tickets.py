import logging
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

from .. import db
from ..utils import (
    ADMIN_IDS,
    ALL_ADMINS,
    PROBLEMS,
    STATUS_OPTIONS,
    USER_MAIN_MENU,
    ADMIN_MAIN_MENU,
    CANCEL_KEYBOARD,
    format_kyiv_time,
    log,
    STATE_ROW,
    STATE_COMP,
    STATE_PROBLEM_MENU,
    STATE_CUSTOM_DESC,
)


async def start_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat

    await db.add_user(user.id, user.full_name)

    chat_type = getattr(chat, "type", "private") if chat else "private"
    is_private_chat = chat_type == "private"
    is_admin = user.id in ADMIN_IDS

    menu = ADMIN_MAIN_MENU if is_private_chat and is_admin else USER_MAIN_MENU
    await update.message.reply_text(
        "Привет! Выберите действие:",
        reply_markup=ReplyKeyboardMarkup(menu, resize_keyboard=True),
    )

    if is_admin and not is_private_chat:
        if not ctx.user_data.get("admin_private_prompt_sent"):
            try:
                await ctx.bot.send_message(
                    chat_id=user.id,
                    text=(
                        "Админ-панель доступна только в личном чате. "
                        "Откройте диалог с ботом, чтобы воспользоваться ей."
                    ),
                    reply_markup=ReplyKeyboardMarkup(
                        ADMIN_MAIN_MENU, resize_keyboard=True
                    ),
                )
            except Exception as exc:  # pragma: no cover - depends on Telegram API
                log.debug("Не удалось отправить приватное меню админу %s: %s", user.id, exc)
            ctx.user_data["admin_private_prompt_sent"] = True

    return ConversationHandler.END


async def start_conversation(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "Введите номер ряда (1–6):", reply_markup=CANCEL_KEYBOARD
    )
    return STATE_ROW


async def handle_cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    message = getattr(update, "message", None)
    text = (getattr(message, "text", None) or "").strip()
    if text == "Отмена":
        result = await cancel(update, ctx)
        return result if result is not None else ConversationHandler.END
    return None


async def row_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    cancel_result = await handle_cancel(update, ctx)
    if cancel_result:
        return cancel_result
    txt = update.message.text.strip()
    if not txt.isdigit() or not (1 <= int(txt) <= 6):
        await update.message.reply_text(
            "Неверный ряд. Введите 1–6:", reply_markup=CANCEL_KEYBOARD
        )
        return STATE_ROW
    ctx.user_data["row"] = txt
    await update.message.reply_text(
        "Введите номер компьютера:", reply_markup=CANCEL_KEYBOARD
    )
    return STATE_COMP


async def comp_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    cancel_result = await handle_cancel(update, ctx)
    if cancel_result:
        return cancel_result
    txt = update.message.text.strip()
    row = int(ctx.user_data["row"])
    max_comp = 9 if row in (5, 6) else 10
    if not txt.isdigit() or not (1 <= int(txt) <= max_comp):
        await update.message.reply_text(
            f"Неверный комп. Введите 1–{max_comp}:",
            reply_markup=CANCEL_KEYBOARD,
        )
        return STATE_COMP
    ctx.user_data["row"] = str(row)
    ctx.user_data["comp"] = txt
    ctx.user_data["row_comp"] = f"{row}/{txt}"
    kb = [PROBLEMS[i : i + 2] for i in range(0, len(PROBLEMS), 2)] + [["Отмена"]]
    await update.message.reply_text(
        "Выберите тип проблемы:",
        reply_markup=ReplyKeyboardMarkup(
            kb, one_time_keyboard=True, resize_keyboard=True
        ),
    )
    return STATE_PROBLEM_MENU


async def problem_menu_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    cancel_result = await handle_cancel(update, ctx)
    if cancel_result:
        return cancel_result
    ch = update.message.text.strip()
    if ch not in PROBLEMS:
        await update.message.reply_text(
            "Выберите проблему из списка:", reply_markup=CANCEL_KEYBOARD
        )
        return STATE_PROBLEM_MENU
    ctx.user_data["problem"] = ch
    await update.message.reply_text(
        "Опишите свою проблему кратко:", reply_markup=CANCEL_KEYBOARD
    )
    return STATE_CUSTOM_DESC


async def custom_desc_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    cancel_result = await handle_cancel(update, ctx)
    if cancel_result:
        return cancel_result
    txt = update.message.text.strip()
    ctx.user_data["description"] = txt
    return await send_request(update, ctx)


async def send_request(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    rowc = ctx.user_data["row_comp"]
    prob = ctx.user_data["problem"]
    desc = ctx.user_data["description"]
    user = update.effective_user

    req_id = await db.add_ticket(rowc, prob, desc, user.full_name, user.id)

    await update.message.reply_text(
        f"✅ Запрос #{req_id} зарегистрирован.\nР/К: {rowc}\n{prob}. {desc}",
        reply_markup=ReplyKeyboardMarkup(USER_MAIN_MENU, resize_keyboard=True),
    )

    btns_s = [
        InlineKeyboardButton(s, callback_data=f"status:{req_id}:{s}")
        for s in STATUS_OPTIONS
        if s != "отменено"
    ]
    btn_r = InlineKeyboardButton("Ответить", callback_data=f"reply:{req_id}")
    created = format_kyiv_time((await db.get_ticket(req_id))[7])
    admin_text = (
        f"Новый запрос #{req_id}\n"
        f"{rowc}: {prob}\n"
        f"Описание: {desc}\n"
        f"От: {user.full_name}, {created}"
    )
    markup = InlineKeyboardMarkup([btns_s, [btn_r]])

    for aid in ALL_ADMINS:
        try:
            await ctx.bot.send_message(aid, admin_text, reply_markup=markup)
        except Exception as e:
            log.warning("Не удалось отправить админу %s: %s", aid, e)

    return ConversationHandler.END


async def my_requests(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    rowc = ctx.user_data.get("row_comp", "")
    all_r = await db.list_tickets()
    mine = [r for r in all_r if r[5] == uid and r[1] == rowc]
    if not mine:
        await update.message.reply_text(
            f"У вас нет запросов для {rowc}.",
            reply_markup=ReplyKeyboardMarkup(USER_MAIN_MENU, resize_keyboard=True),
        )
        return
    btns = [
        [InlineKeyboardButton(f"#{r[0]} ({r[1]}) [{r[6]}] {r[2]}", callback_data=f"show:{r[0]}")]
        for r in mine
    ]
    await update.message.reply_text(
        "Ваши запросы — нажмите для подробностей:",
        reply_markup=InlineKeyboardMarkup(btns),
    )


async def show_request(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    rid = int(q.data.split(":")[1])
    r = await db.get_ticket(rid)
    rowc = ctx.user_data.get("row_comp", "")
    if not r or r[5] != q.from_user.id or r[1] != rowc:
        await q.edit_message_reply_markup(None)
        await q.message.reply_text(
            "Не ваш запрос.",
            reply_markup=ReplyKeyboardMarkup(USER_MAIN_MENU, resize_keyboard=True),
        )
        return
    await q.edit_message_reply_markup(None)
    created = format_kyiv_time(r[7])
    detail = (
        f"#{rid} — {r[1]}\n"
        f"Проблема: {r[2]}\n"
        f"Статус: {r[6]}\n"
        f"Создано: {created}"
    )
    if r[6] not in ("готово", "отменено"):
        kb = InlineKeyboardMarkup(
            [[InlineKeyboardButton("Отменить запрос", callback_data=f"cancel_req:{rid}")]]
        )
        await q.message.reply_text(detail, reply_markup=kb)
    else:
        await q.message.reply_text(detail)
    await q.message.reply_text(
        "Главное меню:",
        reply_markup=ReplyKeyboardMarkup(USER_MAIN_MENU, resize_keyboard=True),
    )


async def cancel_request_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    rid = int(q.data.split(":")[1])
    r = await db.get_ticket(rid)
    if not r or r[5] != q.from_user.id:
        await q.edit_message_text("Не удалось отменить.")
        return
    await db.update_status(rid, "отменено")
    await q.edit_message_text(f"Запрос #{rid} отменён.")
    for aid in ALL_ADMINS:
        try:
            await ctx.bot.send_message(
                aid,
                f"🔔 Запрос #{rid} отменён пользователем {q.from_user.full_name}",
            )
        except Exception as e:
            log.warning(
                "Не удалось уведомить админа %s об отмене запроса #%s: %s",
                aid,
                rid,
                e,
            )
    await ctx.bot.send_message(
        q.from_user.id,
        "Главное меню:",
        reply_markup=ReplyKeyboardMarkup(USER_MAIN_MENU, resize_keyboard=True),
    )


async def init_feedback(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    rid = int(q.data.split(":")[1])
    ctx.user_data["feedback_ticket"] = rid
    await q.message.reply_text(
        "Опишите, пожалуйста, что осталось нерешённым:",
        reply_markup=CANCEL_KEYBOARD,
    )


async def handle_feedback_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    rid = ctx.user_data.get("feedback_ticket")
    if not rid:
        return

    cancel_result = await handle_cancel(update, ctx)
    if cancel_result:
        ctx.user_data.pop("feedback_ticket", None)
        return cancel_result

    txt = (update.message.text or "").strip()

    tkt = await db.get_ticket(rid)
    if not tkt:
        await update.message.reply_text(
            "Ошибка: запрос не найден.",
            reply_markup=ReplyKeyboardMarkup(USER_MAIN_MENU, resize_keyboard=True),
        )
        ctx.user_data.pop("feedback_ticket", None)
        return

    await db.update_status(rid, "принято")

    for aid in ALL_ADMINS:
        try:
            await ctx.bot.send_message(aid, f"💬 Фидбэк к запросу #{rid}:\n{txt}")
            btns_s = [
                InlineKeyboardButton(s, callback_data=f"status:{rid}:{s}")
                for s in STATUS_OPTIONS
                if s != "отменено"
            ]
            btn_r = InlineKeyboardButton("Ответить", callback_data=f"reply:{rid}")
            created = format_kyiv_time(tkt[7])
            new_text = (
                f"🔄 Запрос #{rid} возвращён в «принято» после фидбека\n"
                f"{tkt[1]}: {tkt[2]}\n"
                f"Описание: {tkt[3]}\n"
                f"От: {tkt[4]}, {created}"
            )
            await ctx.bot.send_message(
                aid, new_text, reply_markup=InlineKeyboardMarkup([btns_s, [btn_r]])
            )
        except Exception as e:
            log.warning(
                "Не удалось отправить фидбэк админу %s по запросу #%s: %s",
                aid,
                rid,
                e,
            )

    await update.message.reply_text(
        "Спасибо за обратную связь! Возвращаемся в главное меню.",
        reply_markup=ReplyKeyboardMarkup(USER_MAIN_MENU, resize_keyboard=True),
    )
    ctx.user_data.pop("feedback_ticket", None)


async def cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    menu = USER_MAIN_MENU
    user = getattr(update, "effective_user", None)
    if user and getattr(user, "id", None) in ADMIN_IDS:
        menu = ADMIN_MAIN_MENU
    await update.message.reply_text(
        "❌ Отменено.",
        reply_markup=ReplyKeyboardMarkup(menu, resize_keyboard=True),
    )
    ctx.user_data.pop("feedback_ticket", None)
    return ConversationHandler.END
