import logging
import os

# Создаём папку для логов, если её нет
LOG_DIR = "logs"
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

# Настройки логгера
logger = logging.getLogger("IoT-Light System")
logger.setLevel(logging.DEBUG)  # Логируем всё от DEBUG и выше

# Файл для информационных логов
info_handler = logging.FileHandler(os.path.join(LOG_DIR, "info.log"), encoding="utf-8")
info_handler.setLevel(logging.INFO)

# Файл для ошибок
error_handler = logging.FileHandler(os.path.join(LOG_DIR, "errors.log"), encoding="utf-8")
error_handler.setLevel(logging.ERROR)

#
warning_handler = logging.FileHandler(os.path.join(LOG_DIR, "warning.log"), encoding="utf-8")
warning_handler.setLevel(logging.WARNING)

# Формат логов
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
info_handler.setFormatter(formatter)
error_handler.setFormatter(formatter)
warning_handler.setFormatter(formatter)

# Добавляем обработчики
logger.addHandler(info_handler)
logger.addHandler(error_handler)
logger.addHandler(warning_handler)

# Функции для удобного вызова логов
def log_info(message):
    """Логирует информационные сообщения"""
    logger.info(message)

def log_warning(message):
    """Логирует предупреждения"""
    logger.warning(message)

def log_error(message, exc_info=False):
    """Логирует ошибки, можно передать `exc_info=True` для подробностей"""
    logger.error(message, exc_info=exc_info)

