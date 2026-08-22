@echo off
title SmartBOQ Pro
color 0A

set "PYTHON311=C:\Users\acer\AppData\Local\Programs\Python\Python311\python.exe"
set "BACKEND=%~dp0backend"
set "FRONTEND=%~dp0frontend"

echo.
echo  ================================================
echo   SmartBOQ Pro
echo  ================================================

REM Verify Python 3.11
if not exist "%PYTHON311%" (
    echo  ERROR: Python 3.11 not found.
    echo  Download: https://www.python.org/downloads/release/python-3119/
    pause & exit /b 1
)

REM Kill old servers
echo  Stopping old servers...
for /f "tokens=5" %%a in ('netstat -aon 2^>nul ^| findstr ":8000 "') do taskkill /F /PID %%a >nul 2>&1
for /f "tokens=5" %%a in ('netstat -aon 2^>nul ^| findstr ":5173 "') do taskkill /F /PID %%a >nul 2>&1
timeout /t 2 /nobreak >nul

REM Smart DB init — only runs if smartboq.db does NOT exist
cd /d "%BACKEND%"
if not exist "smartboq.db" (
    echo  First run — initialising database...
    "%PYTHON311%" -c "import sys,os; sys.path.insert(0,'.'); os.environ['DATABASE_URL']='sqlite:///./smartboq.db'; os.environ['SECRET_KEY']='local-dev-secret-key-smartboq-pro-2024'; os.environ['ALLOWED_ORIGINS']='*'; [sys.path.insert(0,p) for p in ['C:\\Users\\acer\\AppData\\Local\\Programs\\Python\\Python311\\Lib\\site-packages'] if p not in sys.path]; from app.db.base import Base,engine; import app.models; Base.metadata.create_all(bind=engine); from app.scripts.seed_data import run; run(); print('DB ready!')"
    if errorlevel 1 (
        echo  DB init failed. Check Python 3.11 installation.
        pause & exit /b 1
    )
) else (
    echo  [OK] Database exists — skipping init (your data is safe)
)

REM Start backend with auto-restart
echo  Starting backend on port 8000...
start "SmartBOQ Backend" cmd /k "cd /d "%BACKEND%" & :loop & "%PYTHON311%" start_py311.py & echo Backend stopped, restarting in 5s... & timeout /t 5 /nobreak ^>nul & goto loop"
timeout /t 8 /nobreak >nul

REM Start frontend
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
echo   ------------------------------------------------
echo   Admin:    admin@smartboq.com / Admin@1234
echo   ================================================
echo.
start "" "http://localhost:5173"
echo  [Press any key to stop all servers]
pause >nul
taskkill /F /FI "WindowTitle eq SmartBOQ*" >nul 2>&1
echo  Stopped.
