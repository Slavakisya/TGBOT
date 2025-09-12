# -*- coding: utf-8 -*-
import logging

from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

import db
from handlers import tickets, admin, help
from utils import (
    TELEGRAM_TOKEN,
    STATE_ROW,
    STATE_COMP,
    STATE_PROBLEM_MENU,
    STATE_CUSTOM_DESC,
    STATE_REPLY,
    STATE_BROADCAST,
    STATE_ARCHIVE_DATE,
    STATE_STATS_DATE,
    STATE_CRM_EDIT,
    STATE_SPEECH_EDIT,
    STATE_FEEDBACK_TEXT,
)


async def on_startup(app):
    app.bot_data["db_conn"] = await db.connect()
    await db.init_db()
    await app.bot.delete_webhook(drop_pending_updates=True)
    me = await app.bot.get_me()
    logging.getLogger("helpdesk_bot").info(
        f"✅ Logged in as @{me.username} ({me.id}). Polling…"
    )


async def on_shutdown(app):
    await db.close()


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s :: %(message)s",
)
log = logging.getLogger("helpdesk_bot")


def main():
    app = (
        Application.builder()
        .token(TELEGRAM_TOKEN)
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

    conv_reply = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin.init_reply, pattern=r"^reply:\\d+$")],
        states={
            STATE_REPLY: [
                MessageHandler(filters.Regex("^Отмена$"), tickets.cancel),
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin.handle_reply),
            ]
        },
        fallbacks=[
            CommandHandler("cancel", tickets.cancel),
            MessageHandler(filters.Regex("^Отмена$"), tickets.cancel),
        ],
    )

    conv_broadcast = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^Отправить всем сообщение$"), admin.init_broadcast)],
        states={
            STATE_BROADCAST: [
                MessageHandler(filters.Regex("^Отмена$"), tickets.cancel),
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin.handle_broadcast),
            ]
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
            CommandHandler("cancel", tickets.cancel),
            MessageHandler(filters.Regex("^Отмена$"), tickets.cancel),
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
            CommandHandler("cancel", tickets.cancel),
            MessageHandler(filters.Regex("^Отмена$"), tickets.cancel),
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
            CommandHandler("cancel", tickets.cancel),
            MessageHandler(filters.Regex("^Отмена$"), tickets.cancel),
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
            CommandHandler("cancel", tickets.cancel),
            MessageHandler(filters.Regex("^Отмена$"), tickets.cancel),
        ],
    )

    conv_feedback = ConversationHandler(
        entry_points=[CallbackQueryHandler(tickets.init_feedback, pattern=r"^feedback:\\d+$")],
        states={
            STATE_FEEDBACK_TEXT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, tickets.handle_feedback_text),
                MessageHandler(filters.Regex("^Отмена$"), tickets.cancel),
            ]
        },
        fallbacks=[
            CommandHandler("cancel", tickets.cancel),
            MessageHandler(filters.Regex("^Отмена$"), tickets.cancel),
        ],
    )

    app.add_handler(conv_ticket)
    app.add_handler(conv_reply)
    app.add_handler(conv_broadcast)
    app.add_handler(conv_archive)
    app.add_handler(conv_stats)
    app.add_handler(conv_crm)
    app.add_handler(conv_speech)
    app.add_handler(conv_feedback)

    app.add_handler(CommandHandler("start", tickets.start_menu))
    app.add_handler(MessageHandler(filters.Regex("^Мои запросы$"), tickets.my_requests))

    app.add_handler(MessageHandler(filters.Regex("^Справка$"), help.help_menu))
    app.add_handler(MessageHandler(filters.Regex("^Правила телефонии$"), help.rules_handler))
    app.add_handler(MessageHandler(filters.Regex("^Ссылки для работы$"), help.links_handler))
    app.add_handler(MessageHandler(filters.Regex("^Спич$"), help.speech_handler))
    app.add_handler(MessageHandler(filters.Regex("^CRM$"), help.crm_handler))
    app.add_handler(MessageHandler(filters.Regex("^Назад$"), help.back_to_main))

    app.add_handler(MessageHandler(filters.Regex("^Все запросы$"), admin.all_requests_cmd))
    app.add_handler(MessageHandler(filters.Regex("^Очистить все запросы$"), admin.clear_requests_admin))
    app.add_handler(MessageHandler(filters.Regex("^Благодарности$"), admin.show_thanks_count))

    app.add_handler(CallbackQueryHandler(tickets.show_request, pattern=r"^show:\\d+$"))
    app.add_handler(CallbackQueryHandler(tickets.cancel_request_callback, pattern=r"^cancel_req:\\d+$"))
    app.add_handler(CallbackQueryHandler(admin.status_callback, pattern=r"^status:\\d+:"))
    app.add_handler(CallbackQueryHandler(admin.handle_thanks, pattern=r"^thanks:\\d+$"))

    log.info("🚀 Bot starting polling…")
    app.run_polling(close_loop=False)


if __name__ == "__main__":
    main()
