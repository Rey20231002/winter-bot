@echo off
cd /d E:\winter\AstrBot

for /f "tokens=5" %%a in ('netstat -ano ^| findstr :6185 ^| findstr LISTENING') do (
    taskkill /F /PID %%a >nul 2>&1
)

echo Starting Winter Bot...
.venv\Scripts\python.exe main.py
pause
