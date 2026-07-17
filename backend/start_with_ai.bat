@echo off
title SmartBOQ Pro Backend WITH AI Models
color 0A

set PYTHON312="C:\Program Files\QGIS 3.44.11\apps\Python312\python.exe"
set BACKEND_DIR=%~dp0

echo Starting SmartBOQ Pro backend with TensorFlow AI support...
echo Python: %PYTHON312%
echo.
echo Checking TensorFlow...
%PYTHON312% -c "import tensorflow as tf; print('TensorFlow', tf.__version__, 'ready')" 2>nul
if errorlevel 1 (
    echo TensorFlow not found! Run install_tf.bat first.
    pause
    exit /b 1
)

echo Checking model files...
if exist "%BACKEND_DIR%ml_models\ResNet50_model.h5" (
    echo  ResNet50_model.h5 - FOUND
) else (
    echo  ResNet50_model.h5 - NOT FOUND (concrete crack model)
)
if exist "%BACKEND_DIR%ml_models\VGG16_model.h5" (
    echo  VGG16_model.h5 - FOUND
) else (
    echo  VGG16_model.h5 - NOT FOUND
)
if exist "%BACKEND_DIR%ml_models\InceptionV3_model.h5" (
    echo  InceptionV3_model.h5 - FOUND
) else (
    echo  InceptionV3_model.h5 - NOT FOUND
)
if exist "%BACKEND_DIR%ml_models\crack_model.h5" (
    echo  crack_model.h5 - FOUND (pothole model)
) else (
    echo  crack_model.h5 - NOT FOUND
)
echo.

cd /d "%BACKEND_DIR%"
%PYTHON312% start_local_py312.py
