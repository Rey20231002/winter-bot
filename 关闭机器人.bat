@echo off
echo Stopping Winter QQ Robot...

set killed=0
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :6185 ^| findstr LISTENING') do (
    taskkill /F /PID %%a >nul 2>&1
    echo Killed AstrBot (PID: %%a)
    set killed=1
)

if %killed%==0 (
    echo No process found on port 6185. Bot may already be stopped.
)

pause
