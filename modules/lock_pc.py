import os

def run():
    print("Блокирую компьютер.")
    try:
        os.system("rundll32.exe user32.dll,LockWorkStation")
    except Exception as e:
        print("Ошибка при блокировке ПК:", e)
