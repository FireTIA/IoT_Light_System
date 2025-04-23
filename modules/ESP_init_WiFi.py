import os
import serial
import requests
import threading
import concurrent.futures
import time
from urllib.parse import quote
import json
from colorama import init, Fore, Back, Style


# Чтение настроек из файла Setting.json
try: 
    with open("Setting.json", "r", encoding="utf-8") as f:
        settings = json.load(f)
except FileNotFoundError:
    print(f"[ESP_Init_WiFi-{Fore.LIGHTYELLOW_EX}WARNING{Fore.RESET}] Файл Setting.json не найден. Используется секретный ключ по умолчанию.")
    settings = {}



# Секретный ключ для доступа к ESP32 (URL-encoded)
secret_key_get = settings.get("esp_secret_key", "ESP_Password")
SECRET_KEY = quote(secret_key_get)


# Подсеть, в которой будут сканироваться устройства
SUBNET = "192.168.3."  # адаптируй под свою сеть

# Порт, на котором работает ESP32 (обычно 80)
ESP_PORT = 80

# Время ожидания отклика от устройства (в секундах)
REQUEST_TIMEOUT = 5



def check_device(ip):
    try:
        url = f"http://{ip}:{ESP_PORT}/iot-ls-discovery?key={SECRET_KEY}"
        response = requests.get(url, timeout=REQUEST_TIMEOUT)
        if response.status_code == 200 and "Support IoT LS" in response.text:
            print(f"{Fore.LIGHTGREEN_EX}[ESPi-Scan]{Fore.RESET} Найдено устройство: {ip} → {response.text.strip()}")
            return (ip, response.text.strip())
    except Exception as e:
        # Можно раскомментировать для отладки: print(f"[DEBUG] {ip}: {e}")
        return None

def scan_subnet(subnet=SUBNET):
    print(f"{Fore.LIGHTCYAN_EX}[ESPi * ]{Fore.RESET} Поиск ESP32 в локальной сети...")
    found_devices = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=100) as executor:
        futures = [executor.submit(check_device, f"{subnet}{i}") for i in range(1, 255)]
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            if result:
                found_devices.append(result)
    print(f"{Fore.LIGHTGREEN_EX}[ESPi ~ ]{Fore.RESET} Найдено устройств: {len(found_devices)}")
    return found_devices

def start_scan_loop():
    global latest_wifi_esp_ip
    while True:
        devices = scan_subnet()
        if devices:
            # Сохраняем IP первого найденного устройства
            latest_wifi_esp_ip = devices[0][0]
        for ip, info in devices:
            print(f"\n \t{Fore.LIGHTGREEN_EX}[ESPi + ]{Fore.RESET}\n |IP→ {ip} \n |Info→ {info}")
        time.sleep(300)

latest_wifi_esp_ip = None

def get_latest_esp_ip():
    return latest_wifi_esp_ip

# Это можно вызывать из main.py в отдельном потоке:
def start_esp_discovery_thread():
    threading.Thread(target=start_scan_loop, daemon=True).start()

# Пример использования при запуске вручную
if __name__ == "__main__":
    start_esp_discovery_thread()
    # Чтобы поток не завершался сразу
    while True:
        time.sleep(1)
