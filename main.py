from flask import Flask, request
from cryptography.fernet import Fernet, InvalidToken
import subprocess
import json
import os
import sys
import time
import socket
import threading
import base64

app = Flask(__name__)



# Настройки
with open("security.json", "r") as f:
    config = json.load(f)

FERNET_KEY = config["FERNET_KEY"].encode()

try:
    Fernet(FERNET_KEY)
except ValueError:
    raise ValueError("Неверный формат FERNET_KEY: должен быть 32 байта в base64")

EXPECTED_KEY = config["EXPECTED_KEY"]
CERT_PATH = "cert.pem"
KEY_PATH  = "key.pem"
IW_PATH = "/data/data/com.termux/files/usr/bin/iw"
BATTERY_STATUS_PATH = "/data/data/com.termux/files/usr/bin/termux-battery-status"
LOCATION_PATH = "/data/data/com.termux/files/usr/bin/termux-location"
OPENSSL = "/data/data/com.termux/files/usr/bin/openssl"

cipher = Fernet(FERNET_KEY)

def validate_key(encrypted_key: str) -> bool:
    try:
        decrypted = cipher.decrypt(encrypted_key.encode()).decode()
        return decrypted == EXPECTED_KEY
    except Exception:
        return False

def get_local_ip():
    """
    Возвращает IP-адрес по умолчанию для исходящего трафика.
    На Android/Termux это будет IP для wlan0.
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # 8.8.8.8:80 не реально соединяется, но нужно для определения локального IP
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return None
    finally:
        s.close()

def generate_cert_for(ip: str):
    subprocess.run([
        OPENSSL, "req", "-x509", "-newkey", "rsa:2048", "-nodes",
        "-days", "365",
        "-keyout", KEY_PATH, "-out", CERT_PATH,
        "-subj", f"/CN={ip}",
        "-addext", f"subjectAltName = IP:{ip}"
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def monitor_ip_and_restart(check_interval=60):
    last_ip = get_local_ip()

    while True:
        time.sleep(check_interval)
        ip = get_local_ip()
        if ip and ip != last_ip:
            print(f"[monitor] IP changed: {last_ip} → {ip}")
            generate_cert_for(ip)       # обновляем cert.pem/key.pem
            os.execv(sys.executable, [sys.executable] + sys.argv)






#--- Разделение







def get_wifi_info():
    try:
        command = f"{IW_PATH} dev wlan0 link"
        result = subprocess.run(
            ["su", "-c", f"sh -c '{command}'"],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            return {"error": "iw failed", "details": result.stderr.strip()}

        info = {
            "connected_to": "Unknown",
            "interface": "wlan0",
            "SSID": "Unknown",
            "freq": "Unknown",
            "RX": "Unknown",
            "TX": "Unknown",
            "signal": "Unknown",
            "rx_bitrate": "Unknown",
            "tx_bitrate": "Unknown"
        }

        for line in result.stdout.splitlines():
            line = line.strip()
            if line.startswith("Connected to"):
                parts = line.split()
                info["connected_to"] = parts[2]
                if "(on" in parts and parts[-1].endswith(")"):
                    info["interface"] = parts[-1][:-1]
            elif line.startswith("SSID:"):
                info["SSID"] = line.split("SSID:")[1].strip()
            elif line.startswith("freq:"):
                info["freq"] = line.split("freq:")[1].strip()
            elif line.startswith("RX:"):
                info["RX"] = line.split("RX:")[1].strip()
            elif line.startswith("TX:"):
                info["TX"] = line.split("TX:")[1].strip()
            elif line.startswith("signal:"):
                info["signal"] = line.split("signal:")[1].strip()
            elif line.startswith("rx bitrate:"):
                info["rx_bitrate"] = line.split("rx bitrate:")[1].strip()
            elif line.startswith("tx bitrate:"):
                info["tx_bitrate"] = line.split("tx bitrate:")[1].strip()

        return info

    except Exception as e:
        return {"error": str(e)}

def get_battery_info():
    try:
        result = subprocess.run(
            ["termux-battery-status"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode != 0:
            return {"error": "termux-battery-status failed", "details": result.stderr.strip()}

        data = json.loads(result.stdout)
        return {
            "percentage":  data.get("percentage"),
            "charging":    data.get("plugged", None) or (data.get("status") == "charging"),
            "voltage":     data.get("voltage"),
            "temperature": data.get("temperature")
        }

    except subprocess.TimeoutExpired:
        return {"error": "timeout waiting for battery status"}
    except Exception as e:
        return {"error": str(e)}


def get_gps_info(provider_selected: str):
    provider = provider_selected.lower()
    if provider not in ("network", "gps"):
        return {
            "gps_enabled": False,
            "error": f"Unsupported provider: {provider_selected}"
        }

    # Параметры запуска для обоих провайдеров
    cmd = ["termux-location", "-p", provider, "-r", "once"]
    timeout = 5 if provider == "network" else 30

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        if result.returncode != 0 or not result.stdout:
            return {
                "gps_enabled": False,
                "provider": provider,
                "error": result.stderr.strip() or "no output"
            }

        data = json.loads(result.stdout)
        return {
            "latitude":  data.get("latitude"),
            "longitude": data.get("longitude"),
            "accuracy":  data.get("accuracy"),
            "provider":  data.get("provider"),  # gps или network
            "gps_enabled": True,
            "method": provider
        }

    except subprocess.TimeoutExpired:
        return {
            "gps_enabled": False,
            "provider": provider,
            "error": f"timeout waiting for {provider} fix"
        }
    except Exception as e:
        return {
            "gps_enabled": False,
            "provider": provider,
            "error": str(e)
        }

def get_wifi_scan_info():
    """
    Запускает `termux-wifi-scaninfo` и возвращает список сетей со всеми доступными параметрами:
    - ssid
    - bssid
    - frequency_mhz
    - rssi (dBm)
    - signal_percent (приблизительная конверсия rssi в %)
    - timestamp
    - channel_bandwidth_mhz
    - center_frequency_mhz
    - capabilities
    """
    try:
        result = subprocess.run(
            ["termux-wifi-scaninfo"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode != 0:
            return {"error": "termux-wifi-scaninfo failed", "details": result.stderr.strip()}

        raw = json.loads(result.stdout)
        networks = []
        for net in raw:
            rssi = net.get("rssi")
            # Конверсия dBm → %: от -100..-50 → 0..100
            if rssi is not None:
                percent = min(max(2 * (rssi + 100), 0), 100)
            else:
                percent = None

            networks.append({
                "ssid":                   net.get("ssid"),
                "bssid":                  net.get("bssid"),
                "frequency_mhz":          net.get("frequency_mhz"),
                "rssi_dbm":               rssi,
                "signal_percent":         percent,
                "timestamp":              net.get("timestamp"),
                "channel_bandwidth_mhz":  net.get("channel_bandwidth_mhz"),
                "center_frequency_mhz":   net.get("center_frequency_mhz"),
                "capabilities":           net.get("capabilities")
            })

        return {"networks": networks}

    except subprocess.TimeoutExpired:
        return {"error": "timeout waiting for wifi scan"}
    except Exception as e:
        return {"error": str(e)}


@app.route('/Status/Wifi_Info/k/<encrypted_key>')
def wifi_info(encrypted_key):
    if not validate_key(encrypted_key):
        return '', 403
    info = get_wifi_info()
    return json.dumps(info), 200, {'Content-Type': 'application/json'}

@app.route('/Status/Battery/k/<encrypted_key>')
def battery_info(encrypted_key):
    if not validate_key(encrypted_key):
        return '', 403
    info = get_battery_info()
    return json.dumps(info), 200, {'Content-Type': 'application/json'}

@app.route('/Status/GPS/<provider_selected>/k/<encrypted_key>')
def gps_info(provider_selected, encrypted_key):
    if not validate_key(encrypted_key):
        return '', 403

    info = get_gps_info(provider_selected)
    return json.dumps(info), 200, {'Content-Type': 'application/json'}

@app.route('/Status/Wifi_Scan/k/<encrypted_key>')
def wifi_scan(encrypted_key):
    if not validate_key(encrypted_key):
        return '', 403
    info = get_wifi_scan_info()
    return json.dumps(info), 200, {'Content-Type': 'application/json'}

if __name__ == '__main__':
    host_ip = get_local_ip() or '0.0.0.0'

    try:
        generate_cert_for(host_ip)
    except Exception as e:
        print(f"[error] Не удалось сгенерировать сертификат: {e}")
        sys.exit(1)

    t = threading.Thread(target=monitor_ip_and_restart, daemon=True)
    t.start()

    print(f"[main] Starting Flask on {host_ip}:5961")
    app.run(host=host_ip, port=5961, ssl_context=(CERT_PATH, KEY_PATH), debug=True)

