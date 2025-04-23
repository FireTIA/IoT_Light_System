import time
import os
import threading



def run_shutdown_time(seconds):
    print(f"\n Выключение запалированно на {seconds / 60} минут \n")
    time.sleep(seconds)
    print(f"\n Выключение \n")
    try:
        os.system(f"shutdown /s /t 10")
        print("f")
    except Exception as e:
        print("Ошибка при выключении ПК:", e)
        err_msg = "Ошибка: " + e
        return err_msg


def run_sleep_mode_pc(timeout):
    time.sleep(timeout)
    try:
        os.system("rundll32.exe powrprof.dll,SetSuspendState 0,1,0")
    except Exception as e:
        print("Ошибка при использования спящего режима ПК:", e)
        err_msg = "Ошибка: " + e
        return err_msg

def run_lock_pc(timeout):
    time.sleep(timeout)
    try:
        os.system("rundll32.exe user32.dll,LockWorkStation")
    except Exception as e:
        print("Ошибка при блокировке ПК:", e)
        err_msg = "Ошибка: " + e
        return err_msg