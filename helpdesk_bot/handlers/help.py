from telegram import Update, ReplyKeyboardMarkup
from telegram.error import BadRequest
from telegram.ext import ContextTypes

from .. import db
from ..utils import HELP_TEXT_RULES, HELP_TEXT_LINKS, log
from . import tickets


async def help_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    kb = [["Правила телефонии", "Ссылки для работы"], ["Спич", "CRM"], ["Назад"]]
    await update.message.reply_text(
        "Выберите раздел справки:",
        reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True),
    )


async def rules_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(HELP_TEXT_RULES)
    await help_menu(update, ctx)


async def links_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(HELP_TEXT_LINKS)
    await help_menu(update, ctx)


async def speech_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    raw = await db.get_setting("speech_text") or ""
    if not raw:
        raw = "Спич пуст."
    chunks = [raw[i : i + 4096] for i in range(0, len(raw), 4096)]
    for chunk in chunks:
        try:
            await update.message.reply_text(chunk)
        except BadRequest as e:
            log.warning("Failed to send speech chunk: %s", e)
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
    chunks = []
    if lines:
        cur = ""
        for ln in lines:
            if len(cur) + len(ln) + 1 > 4096:
                chunks.append(cur.rstrip())
                cur = ln + "\n"
            else:
                cur += ln + "\n"
        if cur:
            chunks.append(cur.rstrip())
    else:
        chunks = ["CRM пуста."]
    for chunk in chunks:
        try:
            await update.message.reply_text(chunk)
        except BadRequest as e:
            log.warning("Failed to send CRM chunk: %s", e)
    await help_menu(update, ctx)


async def back_to_main(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    return await tickets.start_menu(update, ctx)
