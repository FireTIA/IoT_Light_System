import sys
import ctypes
import logging
from typing import Optional, Dict, Any

from PySide6.QtWidgets import (
    QApplication, QWidget, QLabel, QVBoxLayout, QHBoxLayout, QGraphicsOpacityEffect
)
from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QPoint
from PySide6.QtGui import QFont, QColor, QPainter, QBrush

import requests
from bs4 import BeautifulSoup
from colorama import init, Fore, Back, Style

init(autoreset=True)

# Настройка логирования
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Конфигурация подключения к серверу
SERVER_URL = "http://192.168.1.100:5000"
WEATHER_ENDPOINT = "/weather_data"
LOGIN_URL = SERVER_URL + "/login"
PASSWORD = "Password_Req!"

# HTTP-сессия для запросов
session = requests.Session()

def get_csrf_token(html: str) -> Optional[str]:
    """
    Извлекает CSRF-токен из HTML-кода.
    """
    soup = BeautifulSoup(html, "html.parser")
    token_input = soup.find("input", attrs={"name": "csrf_token"})
    if token_input:
        return token_input.get("value")
    return None

def login() -> bool:
    """
    Выполняет авторизацию на сервере, используя CSRF-токен и пароль.
    """
    try:
        res = session.get(LOGIN_URL)
        csrf = get_csrf_token(res.text)
        if not csrf:
            logging.error(f"{Back.WHITE}{Fore.RED}[ERROR]{Fore.RESET}{Back.RESET} CSRF токен не найден")
            return False

        data = {
            "csrf_token": csrf,
            "password": PASSWORD
        }
        headers = {
            "Referer": LOGIN_URL
        }
        r = session.post(LOGIN_URL, data=data, headers=headers)
        if "logout" in r.text.lower() or r.status_code == 200:
            logging.info(f"{Fore.GREEN}[Connect]{Fore.RESET} Авторизация прошла успешно")
            return True
        else:
            logging.error(f"{Back.WHITE}{Fore.RED}[ERROR]{Fore.RESET}{Back.RESET} Неверный пароль или ошибка логина")
            return False
    except Exception as e:
        logging.exception(f"{Back.WHITE}{Fore.RED}[ERROR]{Fore.RESET}{Back.RESET} Ошибка логина: {e}")
        return False

# Константы для настройки эффекта размытия (Windows)
ACCENT_ENABLE_BLURBEHIND = 3
ACCENT_FLAG_ENABLE = 2
WINCOMPATTRIB_ACCENT_POLICY = 19
GRADIENT_COLOR = 0x99000000

class WeatherPanel(QWidget):
    """
    Виджет для отображения информации о погоде с внутреннего и уличного датчиков.
    """
    def __init__(self) -> None:
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(300, 350)

        # Метка статуса подключения
        self.status_label = QLabel("🔄 Подключение...", self)
        self.status_label.setStyleSheet("color: white; font-size: 10px;")
        self.status_label.move(10, 5)
        self.status_label.resize(200, 15)

        self.initUI()
        self.enable_blur()
        self.fade_in()

        self.old_pos: Optional[QPoint] = None

        if login():
            self.status_label.setText("✅ Подключено")
            self.load_weather()
            self.start_timer()
        else:
            self.status_label.setText("❌ Ошибка авторизации")

    def fade_in(self) -> None:
        """
        Реализует эффект плавного появления окна.
        """
        effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(effect)
        anim = QPropertyAnimation(effect, b"opacity")
        anim.setDuration(700)
        anim.setStartValue(0)
        anim.setEndValue(1)
        anim.start()
        # Сохраняем ссылку, чтобы анимация не была уничтожена сборщиком мусора
        self._fade_anim = anim

    def enable_blur(self) -> None:
        """
        Включает эффект размытия фона для окна (только для Windows).
        """
        hwnd = int(self.winId())

        class ACCENTPOLICY(ctypes.Structure):
            _fields_ = [
                ("AccentState", ctypes.c_int),
                ("AccentFlags", ctypes.c_int),
                ("GradientColor", ctypes.c_int),
                ("AnimationId", ctypes.c_int),
            ]

        class WINCOMPATTRDATA(ctypes.Structure):
            _fields_ = [
                ("Attribute", ctypes.c_int),
                ("Data", ctypes.POINTER(ACCENTPOLICY)),
                ("SizeOfData", ctypes.c_size_t),
            ]

        accent = ACCENTPOLICY()
        accent.AccentState = ACCENT_ENABLE_BLURBEHIND
        accent.AccentFlags = ACCENT_FLAG_ENABLE
        accent.GradientColor = GRADIENT_COLOR
        accent.AnimationId = 0

        data = WINCOMPATTRDATA()
        data.Attribute = WINCOMPATTRIB_ACCENT_POLICY
        data.Data = ctypes.pointer(accent)
        data.SizeOfData = ctypes.sizeof(accent)

        try:
            ctypes.windll.user32.SetWindowCompositionAttribute(hwnd, ctypes.byref(data))
        except Exception as e:
            logging.exception("Не удалось включить эффект размытия")

    def initUI(self) -> None:
        """
        Инициализирует графический интерфейс виджета.
        """
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 20, 15, 15)
        layout.setSpacing(6)

        def header(text: str) -> QLabel:
            lbl = QLabel(text)
            lbl.setStyleSheet("color: #00eaff; font-weight: bold;")
            lbl.setFont(QFont("Segoe UI", 10))
            return lbl

        def create_row(label_text: str) -> QHBoxLayout:
            hbox = QHBoxLayout()
            lbl = QLabel(label_text)
            lbl.setStyleSheet("color: #cccccc;")
            lbl.setFont(QFont("Segoe UI", 9))
            value_lbl = QLabel("--")
            # Идентификатор для поиска метки по имени
            value_lbl.setObjectName(label_text.lower().replace(" ", "_"))
            value_lbl.setStyleSheet("color: #ffffff;")
            value_lbl.setFont(QFont("Segoe UI", 9))
            hbox.addWidget(lbl)
            hbox.addStretch()
            hbox.addWidget(value_lbl)
            return hbox

        # Раздел "Погода внутри (BME280)"
        layout.addWidget(header("Погода внутри (BME280)"))
        layout.addLayout(create_row("Температура"))
        layout.addLayout(create_row("Влажность"))
        layout.addLayout(create_row("Давление"))
        layout.addLayout(create_row("Прогноз"))
        layout.addLayout(create_row("Источник"))

        layout.addSpacing(10)
        # Раздел "Погода с улицы (DHT22)"
        layout.addWidget(header("Погода с улицы (DHT22)"))
        layout.addLayout(create_row("Температура (DHT22)"))
        layout.addLayout(create_row("Влажность (DHT22)"))

    def paintEvent(self, event) -> None:
        """
        Отрисовка фона с эффектом полупрозрачного размытия.
        """
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QBrush(QColor(20, 20, 20, 100)))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(self.rect(), 15, 15)

    def start_timer(self) -> None:
        """
        Запускает таймер для периодического обновления данных о погоде.
        """
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.load_weather)
        self.timer.start(10000)

    def load_weather(self):
        try:
            response = session.get(SERVER_URL + WEATHER_ENDPOINT)
            if response.status_code == 200:
                # Если запрос успешен — ставим статус "Подключено"
                self.status_label.setText("✅ Подключено")
                data = response.json()
                self.update_weather(data)
            else:
                # Если сервер ответил, но код не 200
                self.status_label.setText("⚠️ Сервер недоступен")
        except Exception as e:
            # При любой ошибке соединения (таймаут, сеть отвалилась и т.д.)
            logging.exception(f"[Ошибка запроса] {e}")
            self.status_label.setText("❌ Ошибка соединения")

    def update_weather(self, data: Dict[str, Any]) -> None:
        """
        Обновляет значения виджета на основе полученных данных.
        """
        bme = data.get("bme", {})
        dht = data.get("dht", {})

        def update_label(field: str, value: str) -> None:
            lbl = self.findChild(QLabel, field.lower().replace(" ", "_"))
            if lbl:
                lbl.setText(value)

        if bme:
            update_label("Температура", f"{bme.get('temperature', '--')}°C")
            update_label("Влажность", f"{bme.get('humidity', '--')}%")
            update_label("Давление", f"{bme.get('pressure', '--')} hPa")
            update_label("Прогноз", bme.get("forecast_weather", "--"))
            update_label("Источник", bme.get("source", "--"))

        if dht:
            update_label("Температура (DHT22)", f"{dht.get('temperature', '--')}°C")
            update_label("Влажность (DHT22)", f"{dht.get('humidity', '--')}%")

    def mousePressEvent(self, event) -> None:
        self.old_pos = event.globalPos()

    def mouseMoveEvent(self, event) -> None:
        if self.old_pos:
            delta = event.globalPos() - self.old_pos
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.old_pos = event.globalPos()

    def closeEvent(self, event) -> None:
        """
        Останавливает таймер при закрытии окна.
        """
        if hasattr(self, "timer"):
            self.timer.stop()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = WeatherPanel()
    window.show()
    sys.exit(app.exec())
