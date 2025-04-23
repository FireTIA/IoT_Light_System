@echo off

echo Creating virtual environment "venv" for IoT-Light System...
python -m venv venv

echo Activating venv and installing dependencies (if requirements.txt exists)...
call venv\Scripts\activate

if exist requirements.txt (
    pip install -r requirements.txt
) else (
    echo No requirements.txt found. Install packages manually and generate it with "pip freeze > requirements.txt"
)

echo Done.
echo Done.
echo Done.
pause
pause

