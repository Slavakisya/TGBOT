from __future__ import annotations

from datetime import time
from typing import Any

from zoneinfo import ZoneInfo

from telegram.error import BadRequest
from telegram.ext import ContextTypes, JobQueue

from . import db
from .utils import log


KYIV_TZ = ZoneInfo("Europe/Kyiv")


def _parse_time(value: str) -> time:
    try:
        hours_str, minutes_str = value.split(":", 1)
        hours = int(hours_str)
        minutes = int(minutes_str)
        if not (0 <= hours < 24 and 0 <= minutes < 60):
            raise ValueError
        return time(hour=hours, minute=minutes, tzinfo=KYIV_TZ)
    except Exception:
        log.warning(
            "Некорректное время '%s' для ежедневного сообщения. Используется 17:00.",
            value,
        )
        return time(hour=17, minute=0, tzinfo=KYIV_TZ)


async def send_daily_message(context: ContextTypes.DEFAULT_TYPE) -> None:
    job = getattr(context, "job", None)
    data: dict[str, Any] | None = getattr(job, "data", None) if job else None
    message_id = data.get("message_id") if data else None
    if message_id is None:
        return

    chat_id = await db.get_setting("daily_message_chat_id")
    if not chat_id:
        return

    entry = await db.get_daily_message(message_id)
    if not entry:
        return

    text = entry["text"].strip()
    photo_id = entry.get("photo_file_id") or ""
    if not text and not photo_id:
        return

    chat_id_int = int(chat_id)
    parse_mode = entry["parse_mode"] or None
    disable_preview = entry["disable_preview"]

    try:
        if photo_id:
            caption = text or None
            photo_parse_mode = parse_mode if caption else None
            try:
                await context.bot.send_photo(
                    chat_id_int,
                    photo_id,
                    caption=caption,
                    parse_mode=photo_parse_mode,
                )
                return
            except BadRequest as exc:
                error_text = str(exc)
                if "Not enough rights to send photos to the chat" in error_text:
                    if not text:
                        fallback_text = (
                            "⚠️ Не удалось отправить фото ежедневного сообщения "
                            f"#{message_id}: нет прав на отправку изображений."
                        )
                        await context.bot.send_message(
                            chat_id_int,
                            fallback_text,
                            disable_web_page_preview=True,
                        )
                        return
                    log.warning(
                        "Чат %s не позволяет отправлять фото, отправляем только текст.",
                        chat_id,
                    )
                else:
                    log.warning(
                        "Не удалось отправить фото ежедневного сообщения #%s как фото: %s. "
                        "Пробуем отправить как документ.",
                        message_id,
                        exc,
                    )
                    await context.bot.send_document(
                        chat_id_int,
                        photo_id,
                        caption=caption,
                        parse_mode=photo_parse_mode,
                    )
                    return

        await context.bot.send_message(
            chat_id_int,
            entry["text"],
            parse_mode=parse_mode,
            disable_web_page_preview=disable_preview,
        )
    except Exception as exc:  # pragma: no cover - runtime network issues
        log.warning(
            "Не удалось отправить ежедневное сообщение #%s в чат %s: %s",
            message_id,
            chat_id,
            exc,
        )


async def refresh_daily_jobs(job_queue: JobQueue | None) -> None:
    if job_queue is None:
        return

    for job in list(job_queue.jobs()):
        if job.name and job.name.startswith("daily_message:"):
            job.schedule_removal()

    messages = await db.list_daily_messages()
    for message in messages:
        job_queue.run_daily(
            send_daily_message,
            time=_parse_time(message["send_time"]),
            name=f"daily_message:{message['id']}",
            data={"message_id": message["id"]},
        )
    log.info(
        "Запланировано ежедневных сообщений: %s",
        len(messages),
    )
