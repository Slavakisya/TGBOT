from __future__ import annotations

import os
from io import BytesIO
from datetime import time
from typing import Any
from zoneinfo import ZoneInfo

import aiohttp
from telegram.error import BadRequest
from telegram.ext import ContextTypes, JobQueue

from . import db
from .utils import log

KYIV_TZ = ZoneInfo("Europe/Kyiv")
CAPTION_LIMIT = 1024


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


async def _download_to_bytesio(url: str) -> BytesIO:
    """Скачать URL и вернуть BytesIO с корректным 'name', чтобы PTB понял тип файла."""
    timeout = aiohttp.ClientTimeout(total=30)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(url, allow_redirects=True) as resp:
            if resp.status != 200:
                raise BadRequest(f"Bad image url: HTTP {resp.status} {url}")
            data = await resp.read()
            ctype = (resp.headers.get("Content-Type") or "").lower()
            ext = ".jpg"
            if "png" in ctype:
                ext = ".png"
            elif "webp" in ctype:
                ext = ".webp"
            elif "gif" in ctype:
                ext = ".gif"
            bio = BytesIO(data)
            # PTB использует атрибут name, если он есть
            bio.name = f"image{ext}"
            return bio


async def _prepare_media(value: str | None):
    """
    Возвращает одно из:
      - str (telegram file_id) — использовать как есть;
      - BytesIO (если был URL) — отправляем как файл;
      - file object (если локальный путь) — отправляем как файл;
      - None.
    """
    if not value:
        return None

    v = value.strip()
    if v.startswith("http://") or v.startswith("https://"):
        return await _download_to_bytesio(v)

    if os.path.isabs(v) or os.path.exists(v):
        if not os.path.exists(v):
            raise BadRequest(f"File not found: {v}")
        return open(v, "rb")

    # Похоже на telegram file_id
    return v


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

    text = (entry["text"] or "").strip()
    photo_id = (entry.get("photo_file_id") or "").strip()
    if not text and not photo_id:
        return

    chat_id_int = int(chat_id)
    parse_mode = entry.get("parse_mode") or None
    disable_preview = bool(entry.get("disable_preview"))
    photo_is_document = bool(entry.get("photo_is_document"))

    caption = text[:CAPTION_LIMIT] if text else None

    try:
        if photo_id:
            media = await _prepare_media(photo_id)

            # Если помечено как документ — пробуем документом
            if photo_is_document:
                try:
                    await context.bot.send_document(
                        chat_id_int,
                        media,
                        caption=caption,
                        parse_mode=parse_mode if caption else None,
                    )
                    return
                except BadRequest as exc:
                    log.warning(
                        "Ежедневное #%s не ушло как документ: %s — пробуем как фото.",
                        message_id, exc
                    )
                    # fallthrough на отправку фото ниже

            # Пытаемся отправить фото
            try:
                await context.bot.send_photo(
                    chat_id_int,
                    media,
                    caption=caption,
                    parse_mode=parse_mode if caption else None,
                )
                return
            except BadRequest as exc:
                err = str(exc)
                if "Not enough rights to send photos to the chat" in err:
                    if not text:
                        await context.bot.send_message(
                            chat_id_int,
                            (
                                "⚠️ Не удалось отправить фото ежедневного сообщения "
                                f"#{message_id}: нет прав на отправку изображений."
                            ),
                            disable_web_page_preview=True,
                        )
                        return
                    log.warning("Чат %s не позволяет фото — отправляем только текст.", chat_id)
                else:
                    # Фото не получилось — пробуем документом и сохраняем флаг
                    log.warning(
                        "Ежедневное #%s не ушло как фото: %s — пробуем документом.",
                        message_id, exc
                    )
                    try:
                        await context.bot.send_document(
                            chat_id_int,
                            media,
                            caption=caption,
                            parse_mode=parse_mode if caption else None,
                        )
                        await db.update_daily_message(message_id, photo_is_document=True)
                        return
                    except Exception as exc2:
                        log.warning(
                            "Ежедневное #%s не ушло документом: %s — падаем в текст.",
                            message_id, exc2
                        )
                        # fallthrough к тексту

        if text:
            await context.bot.send_message(
                chat_id_int,
                text,
                parse_mode=parse_mode,
                disable_web_page_preview=disable_preview,
            )
    except Exception as exc:  # pragma: no cover
        log.warning(
            "Не удалось отправить ежедневное сообщение #%s в чат %s: %s",
            message_id, chat_id, exc
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
    log.info("Запланировано ежедневных сообщений: %s", len(messages))
