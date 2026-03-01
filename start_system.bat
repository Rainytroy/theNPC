@echo off
set "PROJECT_ROOT=%~dp0"
echo ===================================================
echo       theNPC System Startup Script
echo ===================================================
echo Project Root: %PROJECT_ROOT%

echo [1/4] Starting Claude Service (Port 25999)...
start "1. Claude Service" cmd /k "cd /d %PROJECT_ROOT%claude-local-service && py -3.13 server.py"

echo [2/4] Starting Gemini Service (Port 25998)... (DISABLED)
rem start "2. Gemini Service" cmd /k "cd /d %PROJECT_ROOT%gemini-service && py -3.13 server.py"

echo [3/4] Starting Backend API (Port 26000)...
start "3. Backend API" cmd /k "cd /d %PROJECT_ROOT%backend && py -3.13 main.py"

echo [4/4] Starting Frontend UI (Port 26001)...
start "4. Frontend UI" cmd /k "cd /d %PROJECT_ROOT%frontend && npm run dev"

echo.
echo All services are launching in separate windows.
echo Please wait for them to initialize.
echo.
echo Access the UI at: http://localhost:26001
echo.
pause
