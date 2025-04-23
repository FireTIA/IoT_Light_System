import webbrowser

def run(cmd_data, config):
    url = cmd_data.get("url")
    if not url:
        print("URL не указан для открытия.")
        return
    try:
        webbrowser.open(url)
        print(f"Открываю URL: {url}")
    except Exception as e:
        print("Ошибка при открытии URL:", e)
