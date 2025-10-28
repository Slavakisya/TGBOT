# -*- coding: utf-8 -*-
import inspect
import logging
import os
from datetime import datetime, time
from types import SimpleNamespace

from zoneinfo import ZoneInfo

from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ChatMemberHandler,
    ConversationHandler,
    JobQueue,
    ContextTypes,
    filters,
)

from . import db
from .daily import refresh_daily_jobs, send_daily_message as _run_daily_message
from .predictions import refresh_prediction_job, wish_command
from .handlers import tickets, admin, help, groups
from .utils import TELEGRAM_TOKEN, ConversationState

# Re-export commonly used handlers/constants for test compatibility
PROBLEMS = tickets.PROBLEMS
row_handler = tickets.row_handler
comp_handler = tickets.comp_handler
problem_menu_handler = tickets.problem_menu_handler
custom_desc_handler = tickets.custom_desc_handler
clear_requests_admin = admin.clear_requests_admin


DAILY_MESSAGE_TIME = time(hour=17, minute=0, tzinfo=ZoneInfo("Europe/Kyiv"))


async def send_daily_message(context: ContextTypes.DEFAULT_TYPE):
    """Legacy entry point for cron jobs that used the old settings table."""

    chat_id = await db.get_setting("daily_message_chat_id")
    if not chat_id:
        return

    messages = await db.list_daily_messages()
    if messages:
        kyiv_now = datetime.now(ZoneInfo("Europe/Kyiv")).strftime("%H:%M")
        target = next((msg for msg in messages if msg["send_time"] == kyiv_now), None)
        if target is not None:
            job_context = SimpleNamespace(
                bot=context.bot,
                job=SimpleNamespace(data={"message_id": target["id"]}),
            )
            try:
                await _run_daily_message(job_context)
                return
            except Exception as exc:  # pragma: no cover - runtime network issues
                log.warning(
                    "Не удалось отправить ежедневное сообщение #%s (новый формат): %s",
                    target["id"],
                    exc,
                )
        else:
            log.debug(
                "Нет ежедневного сообщения со временем %s для устаревшего расписания.",
                kyiv_now,
            )

    message = await db.get_setting("daily_message_text")
    if not message:
        return

    parse_mode = await db.get_setting("daily_message_parse_mode") or ""
    disable_preview = await db.get_setting("daily_message_disable_preview") or "0"
    disable_preview_flag = disable_preview == "1"

    try:
        await context.bot.send_message(
            int(chat_id),
            message,
            parse_mode=parse_mode or None,
            disable_web_page_preview=disable_preview_flag,
        )
    except Exception as exc:  # pragma: no cover - runtime network issues
        log.warning(
            "Не удалось отправить ежедневное сообщение в чат %s (устаревший формат): %s",
            chat_id,
            exc,
        )


async def on_startup(app):
    await db.init_db()
    await app.bot.delete_webhook(drop_pending_updates=True)
    me = await app.bot.get_me()
    logging.getLogger("helpdesk_bot").info(
        f"✅ Logged in as @{me.username} ({me.id}). Polling…"
    )
    if app.job_queue is None:
        log.error(
            "Job queue is not configured – ежедневное сообщение отключено. "
            "Установите зависимость python-telegram-bot[job-queue] или запускайте "
            "бота через helpdesk_bot.bot.main()."
        )
        return
    await refresh_daily_jobs(app.job_queue)
    await refresh_prediction_job(app.job_queue)


async def on_shutdown(app):
    pass


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s :: %(message)s",
)
log = logging.getLogger("helpdesk_bot")


def _build_conversation_kwargs():
    """Return keyword arguments supported by the active PTB ConversationHandler."""

    try:
        params = inspect.signature(ConversationHandler.__init__).parameters
    except (TypeError, ValueError):
        # Some stub implementations might not support introspection; fall back to no kwargs.
        return {}

    kwargs = {}

    if os.environ.get("HELPDESK_BOT_FORCE_STUB") == "1" and "per_message" in params:
        kwargs["per_message"] = True

    return kwargs


def _build_coersation_kwnvargs():  # pragma: no cover - legacy compatibility shim
    """Backward compatible alias for older, misspelled helper name."""

    return _build_conversation_kwargs()


_CONVERSATION_KWARGS = _build_conversation_kwargs()


def main():
    job_queue = JobQueue()
    app = (
        Application.builder()
        .token(TELEGRAM_TOKEN)
        .job_queue(job_queue)
        .post_init(on_startup)
        .post_shutdown(on_shutdown)
        .build()
    )

    conv_ticket = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^Создать запрос$"), tickets.start_conversation)],
        states={
            ConversationState.ROW: [
                MessageHandler(filters.Regex("^Отмена$"), tickets.cancel),
                MessageHandler(filters.TEXT & ~filters.COMMAND, tickets.row_handler),
            ],
            ConversationState.COMP: [
                MessageHandler(filters.Regex("^Отмена$"), tickets.cancel),
                MessageHandler(filters.TEXT & ~filters.COMMAND, tickets.comp_handler),
            ],
            ConversationState.PROBLEM_MENU: [
                MessageHandler(filters.Regex("^Отмена$"), tickets.cancel),
                MessageHandler(filters.TEXT & ~filters.COMMAND, tickets.problem_menu_handler),
            ],
            ConversationState.CUSTOM_DESC: [
                MessageHandler(filters.Regex("^Отмена$"), tickets.cancel),
                MessageHandler(filters.TEXT & ~filters.COMMAND, tickets.custom_desc_handler),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", tickets.cancel),
            MessageHandler(filters.Regex("^Отмена$"), tickets.cancel),
        ],
        **_CONVERSATION_KWARGS,
    )

    conv_archive = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^Архив запросов$"), admin.init_archive)],
        states={
            ConversationState.ARCHIVE_DATE: [
                MessageHandler(filters.Regex("^Отмена$"), admin.cancel),
                MessageHandler(filters.Regex(r"^\\d{4}-\\d{2}-\\d{2}$"), admin.archive_by_date_handler),
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin.archive_date_invalid),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", admin.cancel),
            MessageHandler(filters.Regex("^Отмена$"), admin.cancel),
        ],
        **_CONVERSATION_KWARGS,
    )

    conv_stats = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^Статистика$"), admin.stats_start)],
        states={
            ConversationState.STATS_DATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin.stats_show)
            ]
        },
        fallbacks=[
            CommandHandler("cancel", admin.cancel),
            MessageHandler(filters.Regex("^Отмена$"), admin.cancel),
        ],
        **_CONVERSATION_KWARGS,
    )

    conv_crm = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^Изменить CRM$"), admin.edit_crm_start)],
        states={
            ConversationState.CRM_EDIT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin.edit_crm_save)
            ]
        },
        fallbacks=[
            CommandHandler("cancel", admin.cancel),
            MessageHandler(filters.Regex("^Отмена$"), admin.cancel),
        ],
        **_CONVERSATION_KWARGS,
    )

    conv_speech = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^Изменить спич$"), admin.edit_speech_start)],
        states={
            ConversationState.SPEECH_EDIT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin.edit_speech_save)
            ]
        },
        fallbacks=[
            CommandHandler("cancel", admin.cancel),
            MessageHandler(filters.Regex("^Отмена$"), admin.cancel),
        ],
        **_CONVERSATION_KWARGS,
    )

    app.add_handler(conv_ticket)
    app.add_handler(conv_archive)
    app.add_handler(conv_stats)
    app.add_handler(conv_crm)
    app.add_handler(conv_speech)

    app.add_handler(CommandHandler("start", tickets.start_menu))
    app.add_handler(CommandHandler("wish", wish_command))
    app.add_handler(MessageHandler(filters.Regex("^Мои запросы$"), tickets.my_requests))

    app.add_handler(MessageHandler(filters.Regex("^Справка$"), help.help_menu))
    app.add_handler(MessageHandler(filters.Regex("^Правила телефонии$"), help.rules_handler))
    app.add_handler(MessageHandler(filters.Regex("^Ссылки для работы$"), help.links_handler))
    app.add_handler(MessageHandler(filters.Regex("^Спич$"), help.speech_handler))
    app.add_handler(MessageHandler(filters.Regex("^CRM$"), help.crm_handler))
    app.add_handler(MessageHandler(filters.Regex("^Назад$"), help.back_to_main))

    app.add_handler(MessageHandler(filters.Regex("^Заявки$"), admin.show_tickets_menu))
    app.add_handler(MessageHandler(filters.Regex("^Аналитика$"), admin.show_analytics_menu))
    app.add_handler(MessageHandler(filters.Regex("^Настройки$"), admin.show_settings_menu))
    app.add_handler(MessageHandler(filters.Regex("^Ежедневные сообщения$"), admin.daily_message_start))
    app.add_handler(MessageHandler(filters.Regex("^Предсказания$"), admin.predictions_start))
    app.add_handler(
        MessageHandler(
            filters.Regex("^(Обычный текст|Markdown|HTML|Отмена)$"),
            admin.daily_message_set_format,
            block=False,
        ),
        group=1,
    )
    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            admin.daily_message_menu,
            block=False,
        ),
        group=2,
    )
    app.add_handler(
        MessageHandler(
            filters.PHOTO,
            admin.daily_message_save_photo,
            block=False,
        ),
        group=3,
    )
    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            admin.daily_message_save,
            block=False,
        ),
        group=3,
    )
    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            admin.handle_reply,
            block=False,
        ),
        group=4,
    )
    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            tickets.handle_feedback_text,
            block=False,
        ),
        group=5,
    )
    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            admin.predictions_menu,
            block=False,
        ),
        group=6,
    )
    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            admin.predictions_save,
            block=False,
        ),
        group=7,
    )
    app.add_handler(
        MessageHandler(filters.Regex(admin.BACK_BUTTON_PATTERN), admin.back_to_main)
    )

    app.add_handler(MessageHandler(filters.Regex("^Все запросы$"), admin.all_requests_cmd))
    app.add_handler(MessageHandler(filters.Regex("^Очистить все запросы$"), admin.clear_requests_admin))
    app.add_handler(MessageHandler(filters.Regex("^Благодарности$"), admin.show_thanks_count))

    app.add_handler(CallbackQueryHandler(admin.init_reply, pattern=r"^reply:\d+$"))
    app.add_handler(CallbackQueryHandler(tickets.init_feedback, pattern=r"^feedback:\d+$"))
    app.add_handler(CallbackQueryHandler(tickets.show_request, pattern=r"^show:\d+$"))
    app.add_handler(CallbackQueryHandler(tickets.cancel_request_callback, pattern=r"^cancel_req:\d+$"))
    app.add_handler(CallbackQueryHandler(admin.status_callback, pattern=r"^status:\d+:"))
    app.add_handler(CallbackQueryHandler(admin.handle_thanks, pattern=r"^thanks:\d+$"))
    app.add_handler(
        ChatMemberHandler(
            groups.bot_member_update, ChatMemberHandler.MY_CHAT_MEMBER
        )
    )

    log.info("🚀 Bot starting polling…")
    app.run_polling(close_loop=False)


if __name__ == "__main__":
    main()
