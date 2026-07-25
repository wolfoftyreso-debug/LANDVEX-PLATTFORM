@echo off
REM LANDVEX sandbox - Windows launcher. Double-click this file.
setlocal
cd /d "%~dp0"
title LANDVEX sandbox

REM The py launcher ships with python.org installs and picks a modern Python.
where py >nul 2>nul
if %errorlevel%==0 (
    py -3 run.py
    goto done
)

where python >nul 2>nul
if %errorlevel%==0 (
    python run.py
    goto done
)

echo.
echo   Python was not found on this PC.
echo.
echo   Install Python 3.11 or newer from https://python.org/downloads
echo   and tick "Add python.exe to PATH" in the installer, then run this again.
echo.
pause
exit /b 1

:done
if %errorlevel% neq 0 pause
