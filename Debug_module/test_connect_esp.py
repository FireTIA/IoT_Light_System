import requests

ip = "192.168.3.104"
key = "F%40%28%29DCNc2u1F%29%28CNU%23%29"
try:
    resp = requests.get(f"http://{ip}/iot-ls-discovery?key={key}", timeout=1)
    print("Ответ от ESP:", resp.text)
except Exception as e:
    print("Ошибка:", e)