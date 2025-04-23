import serial

# Настройка порта и скорости
ser = serial.Serial('COM5', 9600, timeout=1)

print("[*] Чтение с порта COM5. Нажми Ctrl+C для выхода.")

try:
    while True:
        line = ser.readline().decode('utf-8').strip()
        if line:
            print(f"[Serial] {line}")
except KeyboardInterrupt:
    print("\n[!] Выход.")
    ser.close()
