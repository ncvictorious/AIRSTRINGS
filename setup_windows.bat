@echo off
cd /d "%~dp0"
py -3.11 -m venv .venv
if errorlevel 1 (
 echo ERROR: Please install Python 3.11 from https://www.python.org/downloads/
 pause
 exit /b 1
)
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 (
 echo Installation failed. See errors above.
 pause
 exit /b 1
)
echo Setup complete! Now double-click run_windows.bat
pause
