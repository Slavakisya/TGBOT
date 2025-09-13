# Helpdesk Bot

Перед запуском установите переменные окружения:

- `TELEGRAM_TOKEN` — токен вашего Telegram‑бота.
- `ADMIN_IDS` — список ID администраторов, разделённых запятыми, пробелами или их сочетанием, например `123456,987654` или `123456 987654`.

Бот не запустится, если одна из переменных не задана.

## Запуск

Установите зависимости и выполните:

```bash
pip install python-telegram-bot aiosqlite
python -m helpdesk_bot.bot
```

## Тестирование

Для запуска тестов установите зависимости и выполните:

```bash
pip install pytest pytest-asyncio aiosqlite python-telegram-bot
pytest
```
