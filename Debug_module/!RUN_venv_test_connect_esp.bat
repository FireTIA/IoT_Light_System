@echo off
echo Activating virtual environment...
call ..\venv\Scripts\activate

echo Running test_connect_esp.py...
python test_connect_esp.py

pause
pause
