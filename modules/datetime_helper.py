from datetime import datetime

def get_formatted_datetime():
    """Возвращает текущую дату и время в формате [DD.MM.YYYY-HH:MM]"""
    now = datetime.now()
    return f"[{now.strftime('%d.%m.%Y-%H:%M')}]"

