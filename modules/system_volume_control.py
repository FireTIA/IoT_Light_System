import pythoncom
from ctypes import POINTER, cast
from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

def run(volume_in):
    # Инициализируем COM в потоке
    #pythoncom.CoInitialize()

    try:
        if volume_in is None:
            print("Ошибка: Невозможно определить уровень громкости:", volume_in)
            return

        # Получаем объект управления громкостью
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = cast(interface, POINTER(IAudioEndpointVolume))

        # Если передан mute, выключаем звук
        if isinstance(volume_in, str) and volume_in.lower() == "mute":
            volume.SetMute(1, None)  # 1 - выключить звук
            print("Звук выключен (Mute)")
            return

        try:
            # Преобразуем входное значение в число
            volume_level_in = int(volume_in)
        except ValueError:
            print("Ошибка: Уровень громкости должен быть числом.", volume_in)
            return

        # Если звук замьючен, снимаем mute
        if volume.GetMute():
            volume.SetMute(0, None)  # 0 - включить звук
            print("Звук включен (Unmute)")

        # Ограничиваем значение от 0 до 100
        volume_level = max(0, min(100, volume_level_in))

        # Устанавливаем громкость напрямую в процентах (0.0 - 1.0)
        volume.SetMasterVolumeLevelScalar(volume_level / 100.0, None)

        print(f"Уровень громкости изменён на {volume_level}%")

    except Exception as e:
        print("Ошибка при изменении громкости:", e)

    #finally:
        # Завершаем COM в потоке
        #pythoncom.CoUninitialize()

def get_current_volume():
    # Инициализируем COM в потоке
    #pythoncom.CoInitialize()
    
    try:
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = cast(interface, POINTER(IAudioEndpointVolume))

        # Получаем текущий уровень громкости (0.0 - 1.0) и переводим в проценты
        current_volume = volume.GetMasterVolumeLevelScalar() * 100

        # Ограничиваем, чтобы не было багов
        return max(0, min(100, int(current_volume)))
    
    except Exception as e:
        print("Ошибка при получении громкости:", e)
        return 50  # Если ошибка, возвращаем 50% по умолчанию

    #finally:
        # Завершаем COM в потоке
        #pythoncom.CoUninitialize()
