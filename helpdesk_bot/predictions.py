from __future__ import annotations

import random
from datetime import time

from zoneinfo import ZoneInfo
from telegram import Update
from telegram.ext import ContextTypes, JobQueue

from . import db
from .utils import log

KYIV_TZ = ZoneInfo("Europe/Kyiv")
PREDICTION_JOB_NAME = "daily_predictions"


async def wish_command(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if message is None:
        return

    prediction = await db.get_random_prediction()
    if not prediction or not prediction.strip():
        await message.reply_text("Предсказаний пока нет.")
        return

    await message.reply_text(prediction.strip())


async def broadcast_predictions(context: ContextTypes.DEFAULT_TYPE) -> None:
    predictions = await db.list_predictions()
    if not predictions:
        return

    users = await db.list_users()
    if not users:
        return

    for user_id in users:
        prediction = random.choice(predictions)["text"].strip()
        if not prediction:
            continue
        try:
            await context.bot.send_message(user_id, prediction)
        except Exception as exc:  # pragma: no cover - network issues
            log.warning(
                "Не удалось отправить предсказание пользователю %s: %s", user_id, exc
            )


async def refresh_prediction_job(job_queue: JobQueue | None) -> None:
    if job_queue is None:
        return

    for job in list(job_queue.jobs()):
        if job.name == PREDICTION_JOB_NAME:
            job.schedule_removal()

    job_queue.run_daily(
        broadcast_predictions,
        time=time(hour=9, minute=0, tzinfo=KYIV_TZ),
        name=PREDICTION_JOB_NAME,
    )
