@echo off
title Installing TensorFlow for SmartBOQ Pro AI Features
color 0A
echo.
echo ============================================================
echo  Installing TensorFlow (Python 3.12 via QGIS)
echo  This is required for AI Visual Inspection features
echo ============================================================
echo.

set PYTHON312="C:\Program Files\QGIS 3.44.11\apps\Python312\python.exe"

echo Step 1: Installing TensorFlow (may take 5-10 minutes)...
%PYTHON312% -m pip install tensorflow --user
echo.
echo Step 2: Verifying TensorFlow installation...
%PYTHON312% -c "import tensorflow as tf; print('TensorFlow', tf.__version__, 'installed OK')"
echo.
echo Step 3: Installing all backend packages on Python 3.12...
cd /d "%~dp0"
%PYTHON312% -m pip install fastapi uvicorn[standard] sqlalchemy alembic psycopg2-binary python-jose passlib bcrypt pydantic pydantic-settings email-validator reportlab openpyxl ezdxf python-multipart python-dotenv Pillow numpy python-dateutil --user
echo.
echo ============================================================
echo  Installation complete!
echo  Now run start_with_ai.bat to start with AI support
echo ============================================================
pause
