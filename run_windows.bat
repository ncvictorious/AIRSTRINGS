@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
 echo First run setup_windows.bat
 pause
 exit /b 1
)
.venv\Scripts\python.exe laser_harp.py
pause
