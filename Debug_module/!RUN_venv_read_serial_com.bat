@echo off
echo Activating virtual environment...
call ..\venv\Scripts\activate

echo Running read_serial_com.py...
python read_serial_com.py

pause
pause
