@echo off
title SmartBOQ Pro - Stopping
color 0C
echo.
echo  Stopping SmartBOQ Pro servers...
taskkill /FI "WindowTitle eq SmartBOQ Backend*" /F >nul 2>&1
taskkill /FI "WindowTitle eq SmartBOQ Frontend*" /F >nul 2>&1
taskkill /F /IM uvicorn.exe >nul 2>&1
echo  All servers stopped.
timeout /t 2 /nobreak >nul
