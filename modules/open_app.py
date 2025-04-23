import os

def run(cmd_data, config):
    # Получаем имя текущего пользователя
    user_name = os.getlogin()  # Получаем имя текущего пользователя в системе

    # В cmd_data можем передавать дополнительные параметры, включая путь
    # Заменяем {User_Name} на фактическое имя пользователя
    path = cmd_data.get("path", "").replace("{User_Name}", user_name)

    if not path:
        print("Путь для открытия приложения не указан.")
        return

    try:
        os.startfile(path)  # Открытие файла или ярлыка
        print(f"Открываю приложение: {path}")
    except Exception as e:
        print(f"Ошибка при открытии приложения: {e}")

