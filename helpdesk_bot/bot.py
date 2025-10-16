# -*- coding: utf-8 -*-
import logging
from datetime import time

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
from .daily import refresh_daily_jobs
from .handlers import tickets, admin, help, groups
from .utils import (
    TELEGRAM_TOKEN,
    STATE_ROW,
    STATE_COMP,
    STATE_PROBLEM_MENU,
    STATE_CUSTOM_DESC,
    STATE_ARCHIVE_DATE,
    STATE_STATS_DATE,
    STATE_CRM_EDIT,
    STATE_SPEECH_EDIT,
    ADMIN_BACK_BUTTON,
)

# Re-export commonly used handlers/constants for test compatibility
PROBLEMS = tickets.PROBLEMS
row_handler = tickets.row_handler
comp_handler = tickets.comp_handler
problem_menu_handler = tickets.problem_menu_handler
custom_desc_handler = tickets.custom_desc_handler
clear_requests_admin = admin.clear_requests_admin


DAILY_MESSAGE_TIME = time(hour=17, minute=0, tzinfo=ZoneInfo("Europe/Kyiv"))


async def send_daily_message(context: ContextTypes.DEFAULT_TYPE):
    chat_id = await db.get_setting("daily_message_chat_id")
    message = await db.get_setting("daily_message_text")
    if not chat_id or not message:
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
            "Не удалось отправить ежедневное сообщение в чат %s: %s", chat_id, exc
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


async def on_shutdown(app):
    pass


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s :: %(message)s",
)
log = logging.getLogger("helpdesk_bot")


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
            STATE_ROW: [
                MessageHandler(filters.Regex("^Отмена$"), tickets.cancel),
                MessageHandler(filters.TEXT & ~filters.COMMAND, tickets.row_handler),
            ],
            STATE_COMP: [
                MessageHandler(filters.Regex("^Отмена$"), tickets.cancel),
                MessageHandler(filters.TEXT & ~filters.COMMAND, tickets.comp_handler),
            ],
            STATE_PROBLEM_MENU: [
                MessageHandler(filters.Regex("^Отмена$"), tickets.cancel),
                MessageHandler(filters.TEXT & ~filters.COMMAND, tickets.problem_menu_handler),
            ],
            STATE_CUSTOM_DESC: [
                MessageHandler(filters.Regex("^Отмена$"), tickets.cancel),
                MessageHandler(filters.TEXT & ~filters.COMMAND, tickets.custom_desc_handler),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", tickets.cancel),
            MessageHandler(filters.Regex("^Отмена$"), tickets.cancel),
        ],
    )

    conv_archive = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^Архив запросов$"), admin.init_archive)],
        states={
            STATE_ARCHIVE_DATE: [
                MessageHandler(filters.Regex(r"^\\d{4}-\\d{2}-\\d{2}$"), admin.archive_by_date_handler),
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin.archive_date_invalid),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", admin.cancel),
            MessageHandler(filters.Regex("^Отмена$"), admin.cancel),
        ],
    )

    conv_stats = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^Статистика$"), admin.stats_start)],
        states={
            STATE_STATS_DATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin.stats_show)
            ]
        },
        fallbacks=[
            CommandHandler("cancel", admin.cancel),
            MessageHandler(filters.Regex("^Отмена$"), admin.cancel),
        ],
    )

    conv_crm = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^Изменить CRM$"), admin.edit_crm_start)],
        states={
            STATE_CRM_EDIT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin.edit_crm_save)
            ]
        },
        fallbacks=[
            CommandHandler("cancel", admin.cancel),
            MessageHandler(filters.Regex("^Отмена$"), admin.cancel),
        ],
    )

    conv_speech = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^Изменить спич$"), admin.edit_speech_start)],
        states={
            STATE_SPEECH_EDIT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin.edit_speech_save)
            ]
        },
        fallbacks=[
            CommandHandler("cancel", admin.cancel),
            MessageHandler(filters.Regex("^Отмена$"), admin.cancel),
        ],
        per_message=True,
    )

    app.add_handler(conv_ticket)
    app.add_handler(conv_archive)
    app.add_handler(conv_stats)
    app.add_handler(conv_crm)
    app.add_handler(conv_speech)

    app.add_handler(CommandHandler("start", tickets.start_menu))
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
    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            admin.daily_message_menu,
            block=False,
        )
    )
    app.add_handler(
        MessageHandler(
            filters.Regex("^(Обычный текст|Markdown|HTML|Отмена)$"),
            admin.daily_message_set_format,
            block=False,
        )
    )
    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            admin.daily_message_save,
            block=False,
        ),
        group=1,
    )
    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            admin.handle_reply,
            block=False,
        ),
        group=2,
    )
    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            tickets.handle_feedback_text,
            block=False,
        ),
        group=3,
    )
    app.add_handler(
        MessageHandler(filters.Regex(f"^{ADMIN_BACK_BUTTON}$"), admin.back_to_main)
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
