import os
import json
import time
import datetime
import serial
from threading import Thread
import threading
import matplotlib.pyplot as plt
import sys
import modules.ESP_init_WiFi as ESP_init_WiFi

try:
    import tkinter
except ImportError:
    pass
else:
    def tk_excepthook(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, RuntimeError):
            # Логируем исключения типа "main thread is not in main loop" и пропускаем их
            print("Tkinter RuntimeError пропущен:", exc_value)
        else:
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
    sys.excepthook = tk_excepthook

from colorama import init, Fore, Back, Style

# Чтение настроек из файла Setting.json
try: 
    with open("Setting.json", "r", encoding="utf-8") as f:
        settings = json.load(f)
except FileNotFoundError:
    print(f"[Arduino-Weather-{Fore.LIGHTYELLOW_EX}WARNING{Fore.RESET}] Файл Setting.json не найден. Используется пароль по умолчанию.")
    settings = {}

print(f"\n[Arduino-Weather] Инициализация модуля...\n")

# Параметры подключения к Arduino (их можно перенести сюда или передавать извне)
SERIAL_PORT_ARDUINO = settings.get("SERIAL_PORT_ARDUINO", "COM10")
BAUD_RATE_ARDUINO = settings.get("BAUD_RATE_ARDUINO", 9600)


# Глобальная переменная для хранения источника данных
data_source = "Unknown"

# Глобальные переменные для текущих показателей и истории измерений по двум датчикам
# Для BME280
latest_temperature_bme = None
latest_humidity_bme = None
latest_pressure_bme = None
bme_history = []  # Каждый элемент: {'timestamp': <unix time>, 'temperature': <float>, 'humidity': <float>, 'pressure': <float>}

# Для DHT22
latest_temperature_dht = None
latest_humidity_dht = None
dht_history = []  # Каждый элемент: {'timestamp': <unix time>, 'temperature': <float>, 'humidity': <float>}


def read_from_arduino():
    """
    Функция для считывания данных с Arduino.
    Ожидается, что Arduino отправляет строки вида:
      "[BME280] Temperature: 23.5, Humidity: 45.8, Pressure: 1000.2"
      "[DHT22] Temperature: 22.1, Humidity: 45.2"
    """
    global latest_temperature_bme, latest_humidity_bme, latest_pressure_bme, bme_history
    global latest_temperature_dht, latest_humidity_dht, dht_history

    try:
        global data_source

        ser = serial.Serial(SERIAL_PORT_ARDUINO, BAUD_RATE_ARDUINO, timeout=1)
        time.sleep(2)  # Ждем, пока Arduino перезагрузится
        print(f"\n{Fore.LIGHTBLUE_EX}[Arduino-Weather]{Fore.RESET} Подключен к {Fore.CYAN}{SERIAL_PORT_ARDUINO}{Fore.RESET}, скорость {Fore.CYAN}{BAUD_RATE_ARDUINO}{Fore.RESET}\n")
        
        data_source = f"Serial ({SERIAL_PORT_ARDUINO}|{BAUD_RATE_ARDUINO})"
        while True:
            if ser.in_waiting:
                line = ser.readline().decode('utf-8').strip()
                # Если строка начинается с [BME280]
                if line.startswith("[BME280]"):
                    data_str = line[len("[BME280]"):].strip()
                    # Ожидаемый формат: "Temperature: 23.5, Humidity: 45.8, Pressure: 1000.2"
                    try:
                        parts = data_str.split(',')
                        temp_val = float(parts[0].split(':')[1].strip())
                        hum_val = float(parts[1].split(':')[1].strip())
                        # Если есть данные по давлению
                        press_val = float(parts[2].split(':')[1].strip()) if len(parts) > 2 else None

                        latest_temperature_bme = temp_val
                        latest_humidity_bme = hum_val
                        latest_pressure_bme = press_val

                        ts = time.time()
                        bme_history.append({
                            'timestamp': ts,
                            'temperature': temp_val,
                            'humidity': hum_val,
                            'pressure': press_val
                        })

                        # Оставляем историю за последние 24 часа
                        cutoff = ts - 86400
                        bme_history[:] = [m for m in bme_history if m['timestamp'] >= cutoff]

                    except Exception as e:
                        print(f"\n{Fore.LIGHTBLUE_EX}[Arduino-Weather]{Fore.RESET} {Back.WHITE}{Fore.RED}Ошибка парсинга строки BME280:", line, e, f"{Back.RESET} {Fore.RESET}\n")

                # Если строка начинается с [DHT22]
                elif line.startswith("[DHT22]"):
                    data_str = line[len("[DHT22]"):].strip()
                    # Ожидаемый формат: "Temperature: 22.1, Humidity: 45.2"
                    try:
                        parts = data_str.split(',')
                        temp_val = float(parts[0].split(':')[1].strip())
                        hum_val = float(parts[1].split(':')[1].strip())

                        latest_temperature_dht = temp_val
                        latest_humidity_dht = hum_val

                        ts = time.time()
                        dht_history.append({
                            'timestamp': ts,
                            'temperature': temp_val,
                            'humidity': hum_val
                        })

                        cutoff = ts - 86400
                        dht_history[:] = [m for m in dht_history if m['timestamp'] >= cutoff]

                    except Exception as e:
                        print(f"\n{Fore.LIGHTBLUE_EX}[Arduino-Weather]{Fore.RESET} {Back.WHITE}{Fore.RED}Ошибка парсинга строки DHT22:", line, e, f"{Back.RESET} {Fore.RESET}\n")
            time.sleep(0.1)
    except Exception as e:
        print(f"\n{Fore.LIGHTBLUE_EX}[Arduino-Weather]{Fore.RESET} {Back.WHITE}{Fore.RED}Ошибка при чтении с Arduino:", e, f"{Back.RESET} {Fore.RESET}\n")


def get_stats_for_interval(history, interval_seconds):
    """
    Вычисляет статистику (макс/мин) по температуре и влажности за последние interval_seconds секунд из заданной истории.
    Если в истории есть данные по давлению, также рассчитывает max/min давление.
    """
    current_time = time.time()
    cutoff = current_time - interval_seconds
    relevant = [m for m in history if m['timestamp'] >= cutoff]
    if not relevant:
        return None
    temps = [m['temperature'] for m in relevant]
    hums  = [m['humidity'] for m in relevant]
    result = {
        "temp_max": max(temps),
        "temp_min": min(temps),
        "hum_max": max(hums),
        "hum_min": min(hums)
    }
    if 'pressure' in relevant[0]:
        pressures = [m['pressure'] for m in relevant if m['pressure'] is not None]
        if pressures:
            result["press_max"] = max(pressures)
            result["press_min"] = min(pressures)
    return result


def forecast_weather():
    """
    Пример простого предсказания погоды на основе изменений давления.
    Функция анализирует историю измерений bme_history и рассчитывает изменение давления за последние 30 минут.
    Если данных недостаточно, возвращается соответствующее сообщение.
    """
    if len(bme_history) < 2:
        return "Недостаточно данных для предсказания погоды."
    
    current_data = bme_history[-1]
    past_data = None
    # Ищем запись, которая была не менее чем 30 минут назад (1800 секунд)
    for data in reversed(bme_history):
        if current_data['timestamp'] - data['timestamp'] >= 1800:
            past_data = data
            break
    if past_data is None or current_data['pressure'] is None or past_data['pressure'] is None:
        return "Недостаточно данных для предсказания погоды."
    
    # Вычисляем изменение давления (в гПа) за интервал времени
    delta_time = current_data['timestamp'] - past_data['timestamp']
    pressure_change = current_data['pressure'] - past_data['pressure']
    # Приводим изменение к часовому интервалу
    rate_per_hour = pressure_change / (delta_time / 3600)
    
    # Простой порог для предсказания:
    if rate_per_hour > 1:
        forecast = "Давление растёт, ожидается улучшение погоды."
    elif rate_per_hour < -1:
        forecast = "Давление падает, возможно ухудшение погоды и осадки."
    else:
        forecast = "Изменения давления незначительны, прогноз неясен."
    
    return forecast


def generate_graph(log_entries, log_folder, sensor_label):
    """
    Генерирует график (PNG) за последние 12 часов по данным log_entries.
    График сохраняется в файл с именем "YYYY-MM-DD--HHMMSS--(sensor_label).png"
    """
    cutoff = time.time() - 43200  # последние 12 часов
    entries_12h = [e for e in log_entries if e["timestamp"] >= cutoff]
    if not entries_12h:
        return

    times = [datetime.datetime.fromtimestamp(e["timestamp"]) for e in entries_12h]
    temp_max = [e["temp_max"] for e in entries_12h]
    temp_min = [e["temp_min"] for e in entries_12h]
    hum_max  = [e["hum_max"] for e in entries_12h]
    hum_min  = [e["hum_min"] for e in entries_12h]

    plt.figure(figsize=(10, 6))
    plt.plot(times, temp_max, 'r-', label="Temp Max")
    plt.plot(times, temp_min, 'r--', label="Temp Min")
    plt.plot(times, hum_max, 'b-', label="Hum Max")
    plt.plot(times, hum_min, 'b--', label="Hum Min")
    plt.xlabel("Время")
    plt.ylabel("Значения")
    plt.title(f"Статистика за последние 12 часов ({sensor_label})")
    plt.legend()
    plt.grid(True)

    dt_now = datetime.datetime.now()
    file_time_str = dt_now.strftime("%H%M%S")
    file_name = f"{dt_now.date()}--{file_time_str}--{sensor_label}.png"
    file_path = os.path.join(log_folder, file_name)
    try:
        plt.savefig(file_path)
        print(f"\n{Fore.LIGHTBLUE_EX}[Arduino-Weather-{Fore.LIGHTGREEN_EX}Logger{Fore.LIGHTBLUE_EX}]{Fore.RESET} Сохранён график: {Fore.CYAN}{file_path}{Fore.RESET}\n")
    except Exception as e:
        print(f"\n{Fore.LIGHTBLUE_EX}[Arduino-Weather-{Fore.LIGHTRED_EX}Logger{Fore.LIGHTBLUE_EX}]{Fore.RESET} {Back.WHITE}{Fore.RED}Ошибка сохранения графика:", e, f"{Back.RESET} {Fore.RESET}\n")
    plt.close()


def logging_and_graph_thread():
    """
    Поток для логирования статистики и генерации графиков.
    Каждые 2 часа записывает в JSON-файл статистику за последние 2 часа и генерирует графики за последние 12 часов для каждого датчика.
    При смене дня завершается текущее логирование и создается новый файл.
    """
    # Создаем папки для логов для каждого датчика
    log_folder_bme = os.path.join("Log_Weather", "BME280")
    log_folder_dht = os.path.join("Log_Weather", "DHT22")
    if not os.path.exists(log_folder_bme):
        os.makedirs(log_folder_bme)
    if not os.path.exists(log_folder_dht):
        os.makedirs(log_folder_dht)

    log_entries_bme = []
    log_entries_dht = []
    last_log_time = time.time()
    current_log_date = datetime.date.today()

    while True:
        now = time.time()
        now_date = datetime.date.today()
        # Если прошло 2 часа или сменился день
        if (now - last_log_time) >= 7200 or (now_date != current_log_date):
            stats_bme = get_stats_for_interval(bme_history, 7200)
            stats_dht = get_stats_for_interval(dht_history, 7200)
            dt = datetime.datetime.fromtimestamp(now)
            dt_str = dt.strftime("%Y-%m-%d %H:%M:%S")
            if stats_bme:
                entry_bme = {
                    "timestamp": now,
                    "datetime": dt_str,
                    "temp_max": stats_bme["temp_max"],
                    "temp_min": stats_bme["temp_min"],
                    "hum_max": stats_bme["hum_max"],
                    "hum_min": stats_bme["hum_min"]
                }
                if "press_max" in stats_bme:
                    entry_bme["press_max"] = stats_bme["press_max"]
                    entry_bme["press_min"] = stats_bme["press_min"]
                log_entries_bme.append(entry_bme)
                file_time_str = dt.strftime("%H%M%S")
                file_name_bme = f"{dt.date()}--{file_time_str}--BME280.json"
                file_path_bme = os.path.join(log_folder_bme, file_name_bme)
                try:
                    with open(file_path_bme, "w", encoding="utf-8") as f:
                        json.dump(log_entries_bme, f, indent=2)
                    print(f"\n{Fore.LIGHTBLUE_EX}[Arduino-Weather-{Fore.LIGHTGREEN_EX}Logger{Fore.LIGHTBLUE_EX}]{Fore.RESET} Сохранён лог BME280: {Fore.CYAN}{file_path_bme}{Fore.RESET}\n")
                except Exception as e:
                    print(f"\n{Fore.LIGHTBLUE_EX}[Arduino-Weather-{Fore.LIGHTRED_EX}Logger{Fore.LIGHTBLUE_EX}]{Fore.RESET} {Back.WHITE}{Fore.RED}Ошибка сохранения лога BME280:", e, f"{Back.RESET} {Fore.RESET}\n")
                generate_graph(log_entries_bme, log_folder_bme, "BME280")

            if stats_dht:
                entry_dht = {
                    "timestamp": now,
                    "datetime": dt_str,
                    "temp_max": stats_dht["temp_max"],
                    "temp_min": stats_dht["temp_min"],
                    "hum_max": stats_dht["hum_max"],
                    "hum_min": stats_dht["hum_min"]
                }
                log_entries_dht.append(entry_dht)
                file_time_str = dt.strftime("%H%M%S")
                file_name_dht = f"{dt.date()}--{file_time_str}--DHT22.json"
                file_path_dht = os.path.join(log_folder_dht, file_name_dht)
                try:
                    with open(file_path_dht, "w", encoding="utf-8") as f:
                        json.dump(log_entries_dht, f, indent=2)
                    print(f"\n{Fore.LIGHTBLUE_EX}[Arduino-Weather-{Fore.LIGHTGREEN_EX}Logger{Fore.LIGHTBLUE_EX}]{Fore.RESET} Сохранён лог DHT22: {Fore.CYAN}{file_path_dht}{Fore.RESET}\n")
                except Exception as e:
                    print(f"\n{Fore.LIGHTBLUE_EX}[Arduino-Weather-{Fore.LIGHTRED_EX}Logger{Fore.LIGHTBLUE_EX}]{Fore.RESET} {Back.WHITE}{Fore.RED}Ошибка сохранения лога DHT22:", e, f"{Back.RESET} {Fore.RESET}\n")
                generate_graph(log_entries_dht, log_folder_dht, "DHT22")
                
            last_log_time = now
            if now_date != current_log_date:
                current_log_date = now_date
                log_entries_bme = []
                log_entries_dht = []
        time.sleep(60)

def update_history_from_wifi():
    global latest_temperature_bme, latest_humidity_bme, latest_pressure_bme, data_source    
    import requests
    from urllib.parse import quote
    if ESP_init_WiFi.get_latest_esp_ip():
        try:
            esp_ip = ESP_init_WiFi.get_latest_esp_ip()
            secret_key = settings.get("esp_secret_key", "ESP_Password")
            encoded_key = quote(secret_key)
            url = f"http://{esp_ip}/iot-ls-data?key={encoded_key}"
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                esp_data = response.json()
                latest_temperature_bme = esp_data.get("temperature")
                latest_humidity_bme = esp_data.get("humidity")
                latest_pressure_bme = esp_data.get("pressure")
                data_source = f"Wi-Fi(http://{esp_ip}/)"
                ts = time.time()
                bme_history.append({
                    'timestamp': ts,
                    'temperature': latest_temperature_bme,
                    'humidity': latest_humidity_bme,
                    'pressure': latest_pressure_bme
                })
                cutoff = ts - 86400
                bme_history[:] = [m for m in bme_history if m['timestamp'] >= cutoff]
        except Exception as e:
            print(f"{Back.WHITE}{Fore.LIGHTRED_EX}[ESP-WIFI]{Back.RESET}{Fore.RESET} Ошибка запроса к ESP32: {Fore.YELLOW}{e}{Fore.RESET}")



def esp_wifi_update_loop():
    while True:
        update_history_from_wifi()
        time.sleep(30)  # обновление каждые 30 секунд




def start_threads():
    """
    Запускает потоки для чтения с Arduino и для логирования.
    """
    print(f"\n{Fore.LIGHTBLUE_EX}[Arduino-Weather]{Fore.RESET} Запуск потоков{Fore.LIGHTYELLOW_EX}...{Fore.RESET}\n")
    thread_arduino = Thread(target=read_from_arduino, daemon=True)
    thread_arduino.start()
    threading.Thread(target=esp_wifi_update_loop, daemon=True).start()
    thread_logger = Thread(target=logging_and_graph_thread, daemon=True)
    thread_logger.start()


# Экспортируем переменные и функции, которые могут понадобиться в основном коде
__all__ = [
    "latest_temperature_bme",
    "latest_humidity_bme",
    "latest_pressure_bme",
    "bme_history",
    "latest_temperature_dht",
    "latest_humidity_dht",
    "dht_history",
    "get_stats_for_interval",
    "forecast_weather",
    "start_threads",
    "SERIAL_PORT_ARDUINO",
    "BAUD_RATE_ARDUINO"
]

if __name__ == "__main__":
    start_threads()
    # Простой цикл для вывода последних значений и прогноза погоды в консоль
    try:
        while True:
            print(f"[BME280] Temp: {latest_temperature_bme}, Hum: {latest_humidity_bme}, Press: {latest_pressure_bme}")
            print(f"[DHT22]  Temp: {latest_temperature_dht}, Hum: {latest_humidity_dht}")
            print("Прогноз погоды:", forecast_weather())
            time.sleep(5)
    except KeyboardInterrupt:
        print("Завершение работы.")
