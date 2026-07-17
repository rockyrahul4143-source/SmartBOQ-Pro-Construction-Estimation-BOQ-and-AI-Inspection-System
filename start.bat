@echo off
title SmartBOQ Pro
color 0A
echo.
echo  ================================================
echo   SmartBOQ Pro - Construction Estimation System
echo  ================================================

set "PYTHON312=C:\Program Files\QGIS 3.44.11\apps\Python312\python.exe"
set "BACKEND=%~dp0backend"
set "FRONTEND=%~dp0frontend"
set "ML=%~dp0backend\ml_models"

REM ── Kill anything on port 8000 / 5173 ────────────
echo  Stopping any existing servers...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8000 " 2^>nul') do taskkill /F /PID %%a >nul 2>&1
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":5173 " 2^>nul') do taskkill /F /PID %%a >nul 2>&1
timeout /t 2 /nobreak >nul

REM ── Check AI models ───────────────────────────────
if not exist "%ML%\ResNet50_model.h5" (
    echo  [AI] Models missing - starting training in background...
    start "SmartBOQ Training" cmd /k "cd /d "%BACKEND%" & "%PYTHON312%" train_fast.py & pause"
) else (
    echo  [AI] All 4 AI models found!
)

REM ── Setup database (safe - skips if DB exists) ────
echo  Checking database...
cd /d "%BACKEND%"
"%PYTHON312%" setup_local.py
if errorlevel 1 echo  [INFO] DB already up to date.

REM ── Start backend (with auto-restart wrapper) ─────
echo  Starting backend on port 8000...
start "SmartBOQ Backend" cmd /k "cd /d "%BACKEND%" & :loop & "%PYTHON312%" start_local_py312.py & echo Backend stopped - restarting in 3s... & timeout /t 3 /nobreak & goto loop"
timeout /t 8 /nobreak >nul

REM ── Start frontend ────────────────────────────────
echo  Starting frontend on port 5173...
cd /d "%FRONTEND%"
if not exist "node_modules" (
    echo  Installing npm packages...
    call npm install
)
start "SmartBOQ Frontend" cmd /k "cd /d "%FRONTEND%" & npm run dev"
timeout /t 5 /nobreak >nul

echo.
echo  ================================================
echo   App:      http://localhost:5173
echo   API Docs: http://localhost:8000/docs
echo   Email:    admin@smartboq.com
echo   Password: Admin@1234
echo  ================================================
echo.
start "" "http://localhost:5173"
echo  [Press any key to stop all servers]
pause >nul
taskkill /F /FI "WindowTitle eq SmartBOQ*" >nul 2>&1
echo  All servers stopped.
