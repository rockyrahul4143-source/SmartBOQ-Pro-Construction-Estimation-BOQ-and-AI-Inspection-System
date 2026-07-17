@echo off
title SmartBOQ AI Model Training
color 0A
echo.
echo  ============================================================
echo   SmartBOQ Pro - AI Model Training
echo   Training Concrete Crack + Pothole Detection models
echo  ============================================================
echo.
echo  This will take 20-40 minutes on CPU.
echo  Keep this window open until training is complete.
echo.

set PYTHON312="C:\Program Files\QGIS 3.44.11\apps\Python312\python.exe"
set BACKEND=%~dp0

echo  Step 1: Checking TensorFlow...
%PYTHON312% -c "import tensorflow as tf; print('TensorFlow', tf.__version__, 'ready')"
if errorlevel 1 (
    echo  TensorFlow not found. Installing now...
    %PYTHON312% -m pip install tensorflow --user -q
    echo  TensorFlow installed.
)

echo.
echo  Step 2: Checking OpenCV...
%PYTHON312% -c "import cv2; print('OpenCV ready')" 2>nul
if errorlevel 1 (
    %PYTHON312% -m pip install opencv-python-headless scikit-learn --user -q
)

echo.
echo  Step 3: Starting model training...
cd /d "%BACKEND%"
%PYTHON312% train_and_setup.py

echo.
echo  ============================================================
echo   Training complete! Restart the backend to use AI features.
echo  ============================================================
pause
