from telegram import Update
from telegram.ext import ContextTypes

from .. import db
from ..utils import log


async def bot_member_update(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Track the group chat for the daily reminder when the bot is added or removed."""
    chat = update.effective_chat
    member = update.my_chat_member
    if not chat or not member:
        return

    if chat.type not in {"group", "supergroup"}:
        return

    new_status = member.new_chat_member.status
    if new_status in {"member", "administrator"}:
        chat_id = str(chat.id)
        stored = await db.get_setting("daily_message_chat_id") or ""
        if stored == chat_id:
            return
        await db.set_setting("daily_message_chat_id", chat_id)
        try:
            await ctx.bot.send_message(
                chat.id,
                "Этот чат привязан для ежедневного сообщения в 17:00 (Europe/Kyiv).",
            )
        except Exception as exc:  # pragma: no cover - network errors are logged
            log.warning("Не удалось отправить подтверждение в чат %s: %s", chat.id, exc)
    elif new_status in {"left", "kicked"}:
        stored = await db.get_setting("daily_message_chat_id") or ""
        if stored == str(chat.id):
            await db.set_setting("daily_message_chat_id", "")
