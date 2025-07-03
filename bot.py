import os
print("DEBUG: TELEGRAM_TOKEN = {!r}".format(os.getenv("TELEGRAM_TOKEN")))
import logging
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    ConversationHandler,
    filters,
)
import requests

# Логирование (чтобы видеть ошибки в консоли)
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

# Состояния разговора
STATE_LOCATION, STATE_PROBLEM_MENU, STATE_CUSTOM_DESC = range(3)
PROBLEMS = ["Не включается", "Ошибки ПО", "Медленная работа", "Перегрев", "Другая…"]

# Читаем секреты
TELEGRAM_TOKEN  = os.getenv("TELEGRAM_TOKEN")
SUPPORT_API_KEY = os.getenv("SUPPORT_API_KEY")
SUPPORT_API_URL = "https://support.example.com/api/v1/tickets"

if not TELEGRAM_TOKEN or not SUPPORT_API_KEY:
    raise RuntimeError("Не заданы TELEGRAM_TOKEN или SUPPORT_API_KEY")

# Хендлеры — теперь async
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "Введите номер ряда/компа (например, 2/3):",
        reply_markup=ReplyKeyboardRemove()
    )
    return STATE_LOCATION

async def location_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['location'] = update.message.text.strip()
    keyboard = [PROBLEMS[i:i+2] for i in range(0, len(PROBLEMS), 2)]
    await update.message.reply_text(
        "Выберите тип проблемы или ‘Другая…’:",
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
    )
    return STATE_PROBLEM_MENU

async def problem_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    choice = update.message.text
    if choice == "Другая…":
        await update.message.reply_text(
            "Опишите вашу проблему кратко:", reply_markup=ReplyKeyboardRemove()
        )
        return STATE_CUSTOM_DESC

    context.user_data['description'] = choice
    return await send_to_support(update, context)

async def custom_desc_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['description'] = update.message.text.strip()
    return await send_to_support(update, context)

async def send_to_support(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    loc  = context.user_data['location']
    desc = context.user_data['description']
    user = update.effective_user

    payload = {
        "title": f"ПК {loc} от {user.full_name}",
        "description": desc,
        "requester": {"name": user.full_name, "telegram_id": user.id}
    }
    headers = {
        "Authorization": f"Bearer {SUPPORT_API_KEY}",
        "Content-Type": "application/json"
    }

    try:
        r = requests.post(SUPPORT_API_URL, json=payload, headers=headers, timeout=10)
        r.raise_for_status()
        ticket_id = r.json().get("id", "N/A")
        await update.message.reply_text(f"✅ Запрос #{ticket_id} принят.")
    except Exception as e:
        logging.error("Error sending ticket: %s", e)
        await update.message.reply_text("❌ Ошибка отправки, попробуйте позже.")

    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Отменено.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

def main():
    # Создаём приложение
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            STATE_LOCATION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, location_handler)
            ],
            STATE_PROBLEM_MENU: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, problem_menu_handler)
            ],
            STATE_CUSTOM_DESC: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, custom_desc_handler)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(conv_handler)
    # Запуск бота
    app.run_polling()

if __name__ == "__main__":
    main()
