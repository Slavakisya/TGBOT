import os
import re
import logging
from pathlib import Path
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from telegram import ReplyKeyboardMarkup

log = logging.getLogger("helpdesk_bot")

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

ADMIN_IDS = {int(a) for a in re.split(r"[,\s]+", os.getenv("ADMIN_IDS", "")) if a}
ALL_ADMINS = list(ADMIN_IDS)

if not TELEGRAM_TOKEN or not ADMIN_IDS:
    raise RuntimeError("TELEGRAM_TOKEN или ADMIN_IDS не установлены")


def is_admin(user_id: int) -> bool:
    """Проверяет, является ли id администратора."""
    return user_id in ADMIN_IDS

(
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
) = range(11)

PROBLEMS = [
    "Вопросы по тф",
    "Не работают уши",
    "Не работает микрофон",
    "Не открывается сайт",
    "Комп выключился/завис/сгорел",
    "Настройка шумодава",
    "Плохо работает комп",
    "Плохой инет (или его нет)",
    "Другая проблема",
]

STATUS_OPTIONS = ["принято", "в работе", "готово", "отменено"]
USER_MAIN_MENU = [["Создать запрос", "Мои запросы"], ["Справка"]]
ADMIN_MAIN_MENU = [
    ["Все запросы", "Архив запросов", "Статистика"],
    ["Очистить все запросы", "Отправить всем сообщение", "Изменить CRM", "Изменить спич"],
    ["Благодарности"],
]
CANCEL_KEYBOARD = ReplyKeyboardMarkup([["Отмена"]], resize_keyboard=True)

DATA_DIR = Path(__file__).with_name("data")
try:
    HELP_TEXT_RULES = (DATA_DIR / "rules.txt").read_text(encoding="utf-8")
except FileNotFoundError:
    log.warning("rules.txt not found in %s", DATA_DIR)
    HELP_TEXT_RULES = "Файл rules.txt не найден."

try:
    HELP_TEXT_LINKS = (DATA_DIR / "links.txt").read_text(encoding="utf-8")
except FileNotFoundError:
    log.warning("links.txt not found in %s", DATA_DIR)
    HELP_TEXT_LINKS = "Файл links.txt не найден."


def format_kyiv_time(ts: str) -> str:
    try:
        dt = datetime.fromisoformat(ts).replace(tzinfo=timezone.utc)
        # IANA tz database renamed Europe/Kiev to Europe/Kyiv in 2023
        return dt.astimezone(ZoneInfo("Europe/Kyiv")).strftime("%Y-%m-%d %H:%M:%S")
    except Exception as e:
        log.warning("format_kyiv_time failed: %s", e)
        return ts
