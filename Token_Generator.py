from cryptography.fernet import Fernet
import json
import os

SECURITY_FILE = "security.json"

if os.path.exists(SECURITY_FILE):
    with open(SECURITY_FILE, "r") as f:
        config = json.load(f)
else:
    config = {}

FERNET_KEY_STR = config.get("FERNET_KEY")
EXPECTED_KEY = config.get("EXPECTED_KEY", "7^y9CGwF@HW&;3Ah>g;4awmJI*DUE/!j") 

# Проверка ключа и генерация нового при ошибке
if FERNET_KEY_STR:
    try:
        FERNET_KEY = FERNET_KEY_STR.encode()
        Fernet(FERNET_KEY)
    except ValueError:
        print("Неверный FERNET_KEY, создаю новый.")
        FERNET_KEY = Fernet.generate_key()
        FERNET_KEY_STR = FERNET_KEY.decode()
        config["FERNET_KEY"] = FERNET_KEY_STR
else:
    FERNET_KEY = Fernet.generate_key()
    FERNET_KEY_STR = FERNET_KEY.decode()
    config["FERNET_KEY"] = FERNET_KEY_STR

if "EXPECTED_KEY" not in config:
    config["EXPECTED_KEY"] = EXPECTED_KEY

with open(SECURITY_FILE, "w") as f:
    json.dump(config, f, indent=4)

FERNET_KEY = FERNET_KEY_STR.encode()
cipher = Fernet(FERNET_KEY)

Password = EXPECTED_KEY.encode()
token = cipher.encrypt(Password)
print("Зашифрованный токен:", token.decode())
