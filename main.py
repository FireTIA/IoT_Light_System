from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_from_directory
from flask_socketio import SocketIO
from flask_wtf.csrf import CSRFProtect
from openrgb import OpenRGBClient
from openrgb.utils import RGBColor
from functools import wraps
import os
import json
import time
import threading
from threading import Thread
import psutil
import subprocess
import socket
import re
import platform
from colorama import init, Fore, Back, Style
import pythoncom
import random
import traceback


import serial
import matplotlib.pyplot as plt
import datetime
import webbrowser

from modules import system_RS
from modules import system_volume_control
from modules.logger_m import log_info, log_warning, log_error
from modules.datetime_helper import get_formatted_datetime
import modules.weather_logger as weather_logger
import modules.ESP_init_WiFi as ESP_init_WiFi
from modules.Note_module import note_blueprint, init_directories


#/==============================================================================================
# |
# | Подготовка скрипта
# |
#\==============================================================================================
log_info(f"{get_formatted_datetime()} | Подготовка скрипта")
log_warning(f"{get_formatted_datetime()} | Подготовка скрипта (Это тестовое уведомление)")
log_error(f"{get_formatted_datetime()} | Подготовка скрипта (Это тестовое уведомление)")


init(autoreset=True)

print(f"""\n|={Fore.LIGHTCYAN_EX}IoT-Light System{Fore.RESET} - {Fore.GREEN}WEB{Fore.RESET} \n
      |={Fore.BLUE}V-1.0.0 {Fore.YELLOW}(Pre-Realese b2){Fore.RESET}\n
      |={Fore.GREEN}By {Fore.YELLOW}Fire{Fore.LIGHTRED_EX}TIA{Fore.RESET}\n""")



# Чтение настроек из файла Setting.json
try: 
    log_info(f"{get_formatted_datetime()} | Чтение настроек из файла Setting.json")
    with open("Setting.json", "r", encoding="utf-8") as f:
        settings = json.load(f)
except FileNotFoundError:
    log_warning(f"{get_formatted_datetime()} | Файл Setting.json не найден. Используется пароль по умолчанию.")
    print(f"{Fore.LIGHTYELLOW_EX}[WARNING]{Fore.RESET} Файл Setting.json не найден. Используется пароль по умолчанию.")
    settings = {}

# Пароль для входа на страницу
password_loging = settings.get("password", "Light_2")

# Настройки лимита на ввод пароля
MAX_ATTEMPTS = settings.get("MAX_ATTEMPTS", 5) # Максимальное число попыток
LOCKOUT_TIME = settings.get("LOCKOUT_TIME_SECONDS", 900) # Время блокировки в секундах (например, 15 минут)

# Настройки Flask
Access_Type = settings.get("Acces_type", "Local")
Manual_IP = settings.get("Manual_IP_setup", "127.0.0.1")
Port_WEB = settings.get("Port_WEB", "5000")

# Настройка открытия URL ссылок
Open_URL = settings.get("OpenURL", "False")

# Включение OpenRGB
OpenRGB_s = settings.get("OpenRGB_enabled", "False")

# Включение GpuStat
GpuStat_s = settings.get("GpuStat_enabled", "False")

# Включение ESP_init_WiFi
ESP_IOT_MODULE = settings.get("ESP_IoT", "False")

# Порт и скорость для Arduino
Arduino_Weather_Module = settings.get("Arduino_Weather_Module", "False")
SERIAL_PORT_ARDUINO = settings.get("SERIAL_PORT_ARDUINO", "COM10")
BAUD_RATE_ARDUINO = settings.get("BAUD_RATE_ARDUINO", 9600)

timeout = settings.get("TimeOut_action", 10)

# Чтение настроек из файла Setting.json
try:
    with open("Setting.json", "r", encoding="utf-8") as f:
        settings = json.load(f)
except FileNotFoundError:
    settings = {}

if "secret_key" not in settings:
    log_info(f"{get_formatted_datetime()} | Генерируем 'secret_key' в виде hex-строки")

    settings["secret_key"] = os.urandom(24).hex()  # генерируем ключ в виде hex-строки
    with open("Setting.json", "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=4)

    log_info(f"{get_formatted_datetime()} | Записали 'secret_key' в файл 'Setting.json' ")

app = Flask(__name__) # Инициализация Flask
socketio = SocketIO(app)  # Добавляем поддержку WebSockets
csrf = CSRFProtect(app)


# Здесь вызываем инициализацию директорий для заметок
init_directories(app)
# Регистрируем Blueprint для заметок с префиксом /notes
app.register_blueprint(note_blueprint, url_prefix='/notes')

# Глобальный словарь для хранения количества попыток входа по IP
login_attempts = {}

# Для сессий нужно установить секретный ключ
app.secret_key = settings["secret_key"]

if OpenRGB_s in ["True", "true"]:
    # Подключение к OpenRGB
    try: 
        print(f"[Open{Fore.RED}R{Fore.GREEN}G{Fore.BLUE}B{Fore.RESET}-{Fore.BLUE}API{Fore.RESET}] Подключение к OpenRGB {Fore.MAGENTA}...{Fore.RESET}")
        log_info(f"{get_formatted_datetime()} | Подключение к OpenRGB ")
        client = OpenRGBClient()
        devices = client.devices  # Получаем список устройств

        # Инициализация словаря с доступными режимами для каждого устройства
        device_modes = {device.name: [mode.name for mode in device.modes] for device in devices}
        print(f"[Open{Fore.RED}R{Fore.GREEN}G{Fore.BLUE}B{Fore.RESET}-{Fore.BLUE}API{Fore.RESET}] Подключенно успешно {Fore.GREEN}+{Fore.RESET}")
        log_info(f"{get_formatted_datetime()} | Инициализация словаря с доступными режимами для каждого устройства ")
    except Exception as e:
        log_error(f"{get_formatted_datetime()} | Ошибка подключения к OpenRGB: {e}")
        print(f"[Open{Fore.RED}R{Fore.GREEN}G{Fore.BLUE}B{Fore.RESET}-{Fore.BLUE}API{Fore.RESET}-{Back.WHITE}{Fore.RED}ERROR{Back.RESET}{Fore.RESET}] Ошибка подключения к OpenRGB: {Fore.LIGHTYELLOW_EX}{e}")
else:
    print(f"[Open{Fore.RED}R{Fore.GREEN}G{Fore.BLUE}B{Fore.RESET}-{Fore.BLUE}API{Fore.RESET}] Отключено подключение к OpenRGB <--")

def get_local_ip():
    try:
        log_info(f"{get_formatted_datetime()} | Пытаемся получить IP пк в локальной сети ")
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))  # Пытаемся подключиться к внешнему серверу (но без отправки данных)
            return s.getsockname()[0]  # Получаем локальный IP
    except Exception as e:
        log_error(f"{get_formatted_datetime()} | Ошибка: {e} ")
        return f"{Back.WHITE}{Fore.RED}[GET-Local-IP-ERROR]{Back.RESET}{Fore.RESET} Ошибка: {Fore.YELLOW}{e}{Fore.RESET}"
    

#/==============================================================================================
# |
# | Системы безопасности
# |
#\==============================================================================================


@app.after_request
def add_csrf_token(response):
    response.headers['X-CSRFToken'] = session.get('csrf_token', '')
    return response

def get_mac_address(ip):
    """
    Возвращает MAC-адрес для заданного IP-адреса из локальной сети.
    Сначала посылается ping, чтобы устройство попало в ARP-кеш.
    Затем выполняется команда arp (или ip neigh для Linux) для получения информации.
    """
    system = platform.system().lower()

    log_info(f"{get_formatted_datetime()} | Пытаемся получить MAC-Адрес устройства по IP")
    log_info(f"{get_formatted_datetime()} | Посылаем ping для обновления ARP-кеша")
    # Посылаем ping для обновления ARP-кеша (параметры зависят от ОС)
    try:
        if system == "windows":
            subprocess.call(["ping", "-n", "1", ip], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            subprocess.call(["ping", "-c", "1", ip], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass
    
    log_info(f"{get_formatted_datetime()} | Формируем команду для получения ARP-таблицы")
    # Формируем команду для получения ARP-таблицы
    try:
        if system == "windows":
            # Для Windows используем "arp -a IP"
            command = ["arp", "-a", ip]
        else:
            # Для Linux можно использовать "arp -n IP"
            command = ["arp", "-n", ip]
        output = subprocess.check_output(command, universal_newlines=True)
    except Exception:
        # Если не удалось получить через arp, пытаемся через ip neigh (Linux)
        try:
            command = ["ip", "neigh", "show", ip]
            output = subprocess.check_output(command, universal_newlines=True)
        except Exception:
            return None

    log_info(f"{get_formatted_datetime()} | Ищем MAC-адрес с помощью регулярного выражения")
    # Ищем MAC-адрес с помощью регулярного выражения
    mac_regex = re.compile(r"([0-9A-Fa-f]{2}(?:[:-])){5}[0-9A-Fa-f]{2}")
    match = mac_regex.search(output)
    if match:
        log_info(f"{get_formatted_datetime()} | Получили MAC-адрес: {match.group(0)}")
        return match.group(0)
    log_info(f"{get_formatted_datetime()} | Не удалось получить MAC-адрес")
    return None

def is_locked(ip):
    """Проверяет, заблокирован ли IP-адрес из-за превышения лимита попыток."""
    if ip in login_attempts:
        attempts, last_attempt = login_attempts[ip]
        # Если число попыток достигло максимума и с последней попытки прошло меньше LOCKOUT_TIME секунд, IP заблокирован
        if attempts >= MAX_ATTEMPTS and (time.time() - last_attempt) < LOCKOUT_TIME:
            return True
    return False

def record_attempt(ip):
    """Регистрирует неудачную попытку входа."""
    current_time = time.time()
    if ip in login_attempts:
        attempts, last_attempt = login_attempts[ip]
        # Если с последней попытки прошло достаточно времени, сбрасываем счётчик
        if current_time - last_attempt > LOCKOUT_TIME:
            login_attempts[ip] = (1, current_time)
        else:
            login_attempts[ip] = (attempts + 1, current_time)
    else:
        login_attempts[ip] = (1, current_time)

def reset_attempts(ip):
    """Сбрасывает счётчик попыток для данного IP после успешного входа."""
    if ip in login_attempts:
        del login_attempts[ip]

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            log_info(f"""
┌───────────────────────────────────────────────────
│ {get_formatted_datetime()}
│ IP: {request.remote_addr}
│ Функция: login_required
│ message: Unauthorized access (401)
└───────────────────────────────────────────────────
""")
            return jsonify({'status': 'error', 'message': 'Unauthorized access'}), 401
        return f(*args, **kwargs)
    return decorated_function

def notify_msg_os(input_text):
    os.system(f"msg * '{input_text}'")

#/==============================================================================================
# |
# | Web страницы
# |
#\==============================================================================================


@app.route('/logout')
def logout():
    session.pop('logged_in', None)  # Удаляем ключ авторизации, если он существует
    return redirect(url_for('login'))  # Перенаправляем на страницу входа

@app.route('/login', methods=['GET', 'POST'])
def login():
    ip = request.remote_addr  # Получаем IP-адрес клиента

    if is_locked(ip):
        mac_address = get_mac_address(ip)
        time_left = LOCKOUT_TIME - (time.time() - login_attempts[ip][1])  # Сколько осталось до разблокировки
        time_left = max(1, int(time_left))  # Не уходим в отрицательные числа

        mac_address_formated = mac_address if mac_address else "N/A"

        print(f"\n\t{Fore.LIGHTBLUE_EX}--------[Sec-{Fore.LIGHTRED_EX}WARNING]--------{Fore.RESET}\n \n \tЗабанен: {ip}\n \tMAC: {mac_address_formated}\n \n\t{Fore.LIGHTBLUE_EX}--------[Sec-{Fore.LIGHTRED_EX}WARNING]--------{Fore.RESET}\n")

        log_info(f"""
┌───────────────────────────────────────────────────
│ {get_formatted_datetime()}
│ IP: {request.remote_addr}
│ MAC: {mac_address_formated}
│ Использование: /login  [GET] [POST]
│ Ситуация: Заблокирован из-за брутфорсинга
│ Время блокировки: {LOCKOUT_TIME}
└───────────────────────────────────────────────────
""")
        log_warning(f"""
┌───────────────────────────────────────────────────
│ {get_formatted_datetime()}
│ IP: {request.remote_addr}
│ MAC: {mac_address_formated}
│ Использование: /login  [GET] [POST]
│ Ситуация: Заблокирован из-за брутфорсинга
│ Время блокировки: {LOCKOUT_TIME}
└───────────────────────────────────────────────────
""")

        threats = [
            "Ты в курсе что по Wi-Fi можно отследить мощность сигнала через Airodump-ng? Если нет, то твоя жопа будет бита.. Обернись, падла!",
            "Да я записал твой MAC-Адрес... Стоп, у тебя поддельный MAC? Ну и кто тут 'хакер' у мамы? 🤣",
            "Тебе лучше остановиться... Иначе кое-кого убью 💀",
            "Хочешь стать моим безопасником? Ну хорошо, ФБР выехал по твою душу 🕵️‍♂️",
            "Microtik та у меня, а не TP-Link, и всё логируется! Обломись!",
            "Кто-то уже смотрит на тебя... 👁️",
            "Твои запросы записаны. Думаешь, можешь скрыться? 😈",
            "Браузер уже отправил твои данные. Чистка кэша не поможет. 🖥️",
            "А ты знал, что браузеры хранят уникальный Fingerprint? Теперь знаешь.",
            "Твоя IP-геолокация обновляется в реальном времени. ⏳",
            "Ты точно не хочешь этого... Но уже поздно. 😵‍💫",
            "Где-то на сервере твоя активность уже записана в логах. 📜"
        ]


        return render_template(
            'Error_login_more_auth.html', 
            message="❌ Ты забанен! 🚨",
            ip=ip, 
            mac_address=mac_address if mac_address else "N/A",
            time_left=time_left,
            threat=random.choice(threats)  # Выбираем случайную "угрозу"
        )
        #return jsonify({'IP': ip, 'MAC': mac_address, 'message': 'You banned!', 'App': 'IoT-Light System | Version hidden'})

    if request.method == 'POST':

        password = request.form.get('password')
        if password == password_loging: 
            reset_attempts(ip)  # Сбрасываем попытки при успешном входе
            session['logged_in'] = True
            return redirect(url_for('Menu'))
        else:
            record_attempt(ip)
            return render_template('Error_login.html', message="Неверный пароль. Попробуйте ещё раз.")
    return render_template('login.html')

@app.route('/Menu.html')
def Menu():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    return render_template('Menu.html')

@app.route('/Wall_Desktop.html')
def Wall_Desktop():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    return render_template('WallpaperEngine_back.html')

@app.route('/weather_desktop.html')
def weather_Desktop():
    #if not session.get('logged_in'):
    #    return redirect(url_for('login'))
    
    return render_template('weather_desktop.html')

@app.route('/background')
def get_background():
    return send_from_directory('static/backgrounds', 'main.jpg')


@app.route('/sound/<filename>')
def sound(filename):
    return send_from_directory('static/sound', filename)

@app.route('/Note.html')
def note_page():
    # Проверяем, авторизован ли пользователь
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    return render_template('Note.html')

@app.route('/Pc_control.html')
def Pc_control():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    return render_template('Pc_control.html')

@app.route('/')
def index():
    return render_template('login.html')

@app.route('/RGB_Control.html')
def RGB_Control():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    log_info(f"""
┌───────────────────────────────────────────────────
│ {get_formatted_datetime()}
│ IP: {request.remote_addr}
│ Использование: /RGB_Control  [HTML]
└───────────────────────────────────────────────────
""")

    if OpenRGB_s in ["True", "true"]:
        # Убираем режимы, которые поддерживаются всеми устройствами
        common_modes = set(device_modes[devices[0].name])
        for device in devices[1:]:
            common_modes &= set(device_modes[device.name])

        return render_template('RGB_Control.html', devices=[device.name for device in devices], modes=list(common_modes), device_modes=device_modes)
    else:
        jsonify({'status': 'Info', 'message': 'OpenRGB Offed'})
        return render_template('RGB_Control.html', devices="Offed", modes="Offed", device_modes="Offed")
    
@app.route('/Open_Documentation', methods=['GET'])
def open_documentation():
    return render_template('doc.html')


#/==============================================================================================
# |
# | Взаимодействие с Arduino
# |
#\==============================================================================================





@app.route('/weather', methods=['GET'])
def weather_page():
    """
    Рендерит HTML-страницу с отображением погоды.
    """
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    return render_template('weather.html')

@app.route('/weather_data', methods=['GET'])
@login_required
def weather_data():
    """
    Возвращает актуальную температуру, влажность и статистику для BME280 и DHT22 в JSON.
    """
    log_info(f"""
┌───────────────────────────────────────────────────
│ {get_formatted_datetime()}
│ IP: {request.remote_addr}
│ Использование: /weather_data  [GET]
└───────────────────────────────────────────────────
""")
    # Интервалы для расчёта статистики
    intervals = {
        "1m": 60,
        "5m": 300,
        "15m": 900,
        "30m": 1800,
        "60m": 3600,
        "2h": 7200,
        "4h": 14400,
        "6h": 21600,
        "12h": 43200,
        "24h": 86400
    }
    
    # Расчёт статистики для BME280 и DHT22 по заданным интервалам
    stats_bme = {}
    stats_dht = {}
    for key, seconds in intervals.items():
        stats_bme[key] = weather_logger.get_stats_for_interval(weather_logger.bme_history, seconds)
        stats_dht[key] = weather_logger.get_stats_for_interval(weather_logger.dht_history, seconds)
    
    return jsonify({
        "bme": {
            "temperature": weather_logger.latest_temperature_bme,
            "humidity": weather_logger.latest_humidity_bme,
            "pressure": weather_logger.latest_pressure_bme,
            "stats": stats_bme,
            "forecast_weather": weather_logger.forecast_weather(),
            "source": weather_logger.data_source   # источник данных
        },
        "dht": {
            "temperature": weather_logger.latest_temperature_dht,
            "humidity": weather_logger.latest_humidity_dht,
            "stats": stats_dht
        }
    })

#/==============================================================================================
# |
# | Взаимодействие с пк
# |
#\==============================================================================================

def open_web(inputed):
    if Open_URL in ["True", "true"]:
        webbrowser.open_new_tab(inputed)

# Получение процента загруженности
@app.route('/system_status', methods=['GET'])
@login_required
def system_status():
    # Системные показатели CPU и RAM
    cpu_load = psutil.cpu_percent(interval=1)
    ram_usage = psutil.virtual_memory().percent
    avail_ram_gb = round(psutil.virtual_memory().available / 1024**3, 2)
    physical_cores = psutil.cpu_count(logical=False)
    total_ram_gb = round(psutil.virtual_memory().total / 1024**3, 2)
    
    # Показатели GPU с использованием gpustat
    if GpuStat_s in ["True", "true"]:
        import gpustat # Работает только с NVIDIA!!
        stats = gpustat.new_query()
        if stats.gpus:
            gpu = stats.gpus[0]  # берем первую видеокарту
            gpu_utilization = gpu.utilization  # загрузка GPU в процентах
            gpu_temperature = gpu.temperature  # температура GPU в градусах Цельсия

            if gpu.memory_total:
                gpu_memory_percent = round((gpu.memory_used / gpu.memory_total) * 100, 1)
            else:
                gpu_memory_percent = 0
            gpu_memory_used = gpu.memory_used       # используемая память в МБ
            gpu_memory_total = gpu.memory_total     # общий объём памяти в МБ
        else:
            gpu_utilization = 0
            gpu_temperature = 0
            gpu_memory_percent = 0
            gpu_memory_used = 0
            gpu_memory_total = 0
    else: 
        gpu_utilization = 0.0
        gpu_temperature = 0.0
        gpu_memory_percent = 0.0
        gpu_memory_used = 0.0
        gpu_memory_total = 0.0

    return jsonify({
        "CPU Load": cpu_load,
        "RAM Usage": ram_usage,
        "Available RAM (GB)": avail_ram_gb,
        "Physical CPU Cores": physical_cores,
        "Total RAM (GB)": total_ram_gb,
        "GPU Load": gpu_utilization,
        "GPU Temp (°C)": gpu_temperature,
        "GPU Memory Load (%)": gpu_memory_percent,
        "GPU Memory Used (MB)": gpu_memory_used,
        "GPU Memory Total (MB)": gpu_memory_total
    })

# Функция отправки ПК в спящий режим
@app.route('/set_sleep_pc', methods=['POST'])
@login_required
def set_sleep_pc():
    log_info(f"""
┌───────────────────────────────────────────────────
│ {get_formatted_datetime()}
│ IP: {request.remote_addr}
│ Использование: /set_sleep_pc  [POST]
└───────────────────────────────────────────────────
""")
    jsonify({'status': 'success', 'message': f'Пк будет отправлен в спящий режим через {timeout} секунд'})
    
    t = threading.Thread(target=system_RS.run_sleep_mode_pc, args=(timeout,))
    t.start()


    return jsonify({'status': 'success', 'message': f'Пк был отправлен в спящий режим'})

# Функция отправки ПК в спящий режим
@app.route('/lock_pc', methods=['POST'])
@login_required
def lock_pc():

    log_info(f"""
┌───────────────────────────────────────────────────
│ {get_formatted_datetime()}
│ IP: {request.remote_addr}
│ Использование: /lock_pc  [POST]
└───────────────────────────────────────────────────
""")

    jsonify({'status': 'success', 'message': f'Пк будет отправлен на экран входа через {timeout} секунд'})
    
    
    t = threading.Thread(target=system_RS.run_lock_pc, args=(timeout,))
    t.start()
    
    return jsonify({'status': 'success', 'message': 'ПК отправлен на экран входа'})

# Функция запланированного выключения
shutdown_timer = None
@app.route('/set_shutdown', methods=['POST'])
@login_required
def set_shutdown():
    global shutdown_timer
    data = request.json
    minutes = int(data.get('minutes', 0))

    log_info(f"""
┌───────────────────────────────────────────────────
│ {get_formatted_datetime()}
│ IP: {request.remote_addr}
│ Использование: /set_shutdown  [POST]
│ Аргументы: minutes = {minutes}
└───────────────────────────────────────────────────
""")
    
    if shutdown_timer and shutdown_timer.is_alive():
        return jsonify({'status': 'error', 'message': 'Выключение уже запланировано'})
    
    shutdown_timer = threading.Thread(target=system_RS.run_shutdown_time, args=(minutes * 60,))
    shutdown_timer.start()
    return jsonify({'status': 'success', 'message': f'Выключение пк запланированно'})

# Изменение громкости Windows и мут звука
@app.route('/set_volume', methods=['POST'])
@login_required
def set_volume():
    data = request.json
    volume = data.get('volume')
    mute = data.get('mute', False)
    
    log_info(f"""
┌───────────────────────────────────────────────────
│ {get_formatted_datetime()}
│ IP: {request.remote_addr}
│ Использование: /set_volume  [POST]
│ Аргументы: volume = {volume}
│ Аргументы: mute = {mute}
└───────────────────────────────────────────────────
""")

    if mute:
        system_volume_control.run("mute")
    else:
        system_volume_control.run(volume)
    
    return jsonify({'status': 'success', 'volume': volume, 'mute': mute})

@app.route('/get_volume', methods=['GET'])
@login_required
def get_volume():
    try:
        current_volume = system_volume_control.get_current_volume()
        
        log_info(f"""
┌───────────────────────────────────────────────────
│ {get_formatted_datetime()}
│ IP: {request.remote_addr}
│ Использование: /get_volume  [GET]
│ Аргументы: current_volume = {current_volume}
└───────────────────────────────────────────────────
""")

        return jsonify({'status': 'success', 'volume': current_volume})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})


@app.route('/pc_control')
def pc_control():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    return render_template('pc_control.html')


#/==============================================================================================
# |
# | Взаимодействие с OpenRGB
# |
#\==============================================================================================

@app.route('/set_color', methods=['POST'])
@login_required
def set_color():
    if OpenRGB_s not in ["True", "true"]:
        return jsonify("None")
    
    data = request.json
    color = RGBColor(data['r'], data['g'], data['b'])
    device_name = data.get('device')

    log_info(f"""
┌───────────────────────────────────────────────────
│ {get_formatted_datetime()}
│ IP: {request.remote_addr}
│ Использование: /set_color  [POST]
│ Аргументы: color = {color}
│ Аргументы: device_name = {device_name}
└───────────────────────────────────────────────────
""")
    
    for device in devices:
        if device.name == device_name or device_name == 'All':
            device.set_color(color)
    
    socketio.emit('notification', {'title': 'RGBSyncWeb IoT - RGB', 'message': 'Установлен цвет {color}'})
    return jsonify({'status': 'success', 'color': data})

@app.route('/turn_off', methods=['POST'])
@login_required
def turn_off():
    if OpenRGB_s not in ["True", "true"]:
        return jsonify("None")
    
    log_info(f"""
┌───────────────────────────────────────────────────
│ {get_formatted_datetime()}
│ IP: {request.remote_addr}
│ Использование: /turn_off  [POST]
└───────────────────────────────────────────────────
""")

    for device in devices:
        device.set_color(RGBColor(0, 0, 0))
    return jsonify({'status': 'success', 'message': 'Lights turned off'})



@app.route('/set_mode', methods=['POST'])
@login_required
def set_mode():
    if OpenRGB_s not in ["True", "true"]:
        return jsonify("None")
    
    data = request.json
    mode = data.get('mode')
    device_name = data.get('device')

    log_info(f"""
┌───────────────────────────────────────────────────
│ {get_formatted_datetime()}
│ IP: {request.remote_addr}
│ Использование: /set_mode  [POST]
│ Аргументы: mode = {mode}
│ Аргументы: device_name = {device_name}
└───────────────────────────────────────────────────
""")

    for device in devices:
        if device.name == device_name or device_name == 'All':
            for m in device.modes:
                if m.name == mode:
                    device.set_mode(m)
                    break

    return jsonify({'status': 'success', 'mode': mode})

@app.route('/set_brightness', methods=['POST'])
@login_required
def set_brightness():
    if OpenRGB_s not in ["True", "true"]:
        return jsonify("None")
    data = request.json
    brightness = data.get('brightness')
    device_name = data.get('device')

    log_info(f"""
┌───────────────────────────────────────────────────
│ {get_formatted_datetime()}
│ IP: {request.remote_addr}
│ Использование: /set_brightness  [POST]
│ Аргументы: brightness = {brightness}
│ Аргументы: device_name = {device_name}
└───────────────────────────────────────────────────
""")
    
    for device in devices:
        if hasattr(device, 'max_brightness'):
            max_brightness = device.max_brightness
            new_brightness = int((brightness / 100) * max_brightness)
            device.set_brightness(new_brightness)
    
    return jsonify({'status': 'success', 'brightness': brightness})

@app.route('/get_device_info', methods=['GET'])
@login_required
def get_device_info():
    if OpenRGB_s not in ["True", "true"]:
        return jsonify("None")
    
    log_info(f"""
┌───────────────────────────────────────────────────
│ {get_formatted_datetime()}
│ IP: {request.remote_addr}
│ Использование: /get_device_info  [GET]
└───────────────────────────────────────────────────
""")


    device_name = request.args.get('device', 'All')
    device_info = []

    for device in devices:
        if device.name == device_name or device_name == 'All':
            active_colors = [color for color in device.colors if color.red or color.green or color.blue]

            if active_colors:
                first_color = active_colors[0]  # Берем первый цвет, который не черный
            else:
                first_color = RGBColor(25, 25, 25)  # Если цветов нет, показываем черный

            device_info.append({
                'name': device.name,
                'color': {'r': first_color.red, 'g': first_color.green, 'b': first_color.blue}
            })

    return jsonify(device_info)

@app.route('/get_device_modes', methods=['GET'])
@login_required
def get_device_modes():

    log_info(f"""
┌───────────────────────────────────────────────────
│ {get_formatted_datetime()}
│ IP: {request.remote_addr}
│ Использование: /get_device_modes  [GET]
└───────────────────────────────────────────────────
""")

    if OpenRGB_s not in ["True", "true"]: 
        return jsonify("None")
    device_name = request.args.get('device', 'All')
    available_modes = []

    if device_name == 'All':
        # Если выбрано "Все устройства", получаем общие режимы
        common_modes = set(device_modes[devices[0].name])
        for device in devices[1:]:
            common_modes &= set(device_modes[device.name])
        available_modes = list(common_modes)
    else:
        # Если выбрано конкретное устройство, получаем его режимы
        available_modes = device_modes.get(device_name, [])

    return jsonify(available_modes)



#/==============================================================================================
# |
# | Запуск py скрипта
# |
#\==============================================================================================



if __name__ == '__main__':

    pythoncom.CoInitialize() # (Не помогла) Инициализируем эту фигню что бы не падал код, и не было ошибок при работе с громокстью.. так как это падла ломала чутка скрипт

    if Arduino_Weather_Module in ["True", "true"]:
        weather_logger.start_threads()
    elif Arduino_Weather_Module in ["False", "false"]:
        print(f"[Arduino-Weather] Отключен")
    
    if ESP_IOT_MODULE in ["True", "true"]:
        ESP_init_WiFi.start_esp_discovery_thread()
    elif ESP_IOT_MODULE in ["False", "false"]:
        print(f"[ESP-Init-WiFi] Отключен")

    

    if Access_Type in ["Local"]:
        log_info(f"{get_formatted_datetime()} | Запуск SocketIO > host=127.0.0.1, Port={int(Port_WEB)}")
        
        open_web(f"http://127.0.0.1:{int(Port_WEB)}")
        socketio.run(app, host='127.0.0.1', port=int(Port_WEB), debug=True, use_reloader=False)
        
    elif Access_Type in ["Manual_IP"]:
        log_info(f"{get_formatted_datetime()} | Запуск SocketIO > host={Manual_IP}, Port={int(Port_WEB)}")
        
        open_web(f"http://{Manual_IP}:{int(Port_WEB)}")
        try: 
            socketio.run(app, host=Manual_IP, port=int(Port_WEB), debug=True, use_reloader=False)
        except Exception as e:
            log_error("Server crashed: %s", e)
            log_error(traceback.format_exc())

    else: 
        print("Вы что-то не верно в конфиге указали..\n")
        
        local_ip = get_local_ip()
        
        print(f"IP: {local_ip}")
        print(f"Вы хотите использовать этот локальный IP? [Y/N]")
        
        select = input("> ")
        
        if select.lower() in ["y", "yes", "ye", "да", "д"]:
            print(f"\n ")
            log_info(f"{get_formatted_datetime()} | Запуск SocketIO > host={local_ip}, Port={int(Port_WEB)}")
            open_web(f"http://{local_ip}:{int(Port_WEB)}")
            socketio.run(app, host=local_ip, port=int(Port_WEB), debug=True, use_reloader=False)
        else: 
            log_info(f"{get_formatted_datetime()} | Запуск SocketIO отменяется. Выход из программы")
            print("Вы отказались..")
            exit(1)