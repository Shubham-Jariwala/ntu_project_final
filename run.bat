@echo off
REM ORCID Publication Counter - Windows Launcher

setlocal enabledelayedexpansion

REM Get the directory where this script is located
set DIR=%~dp0

REM Change to the application directory
cd /d "%DIR%"

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo ❌ Python is not installed or not in PATH
    echo.
    echo Please install Python 3.8 or higher from: https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation
    echo.
    pause
    exit /b 1
)

REM Get Python version
for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VER=%%i
echo ✓ Python version: %PYTHON_VER%

REM Check if requirements are installed
echo Checking dependencies...
python -c "import flask; import pandas; import requests" 2>nul
if errorlevel 1 (
    echo.
    echo 📦 Installing required packages (first time only)...
    echo This may take a few moments...
    echo.
    pip install -r requirements.txt
    echo.
)

cls
echo.
echo ╔════════════════════════════════════════════════════════════════╗
echo ║        ORCID Publication Counter - Starting Application        ║
echo ╚════════════════════════════════════════════════════════════════╝
echo.
echo 🌐 Application running at: http://localhost:5000
echo 🔗 Opening in your default browser...
echo ⚠️  Close the browser or press CTRL+C to stop the application
echo.

REM Open browser
start http://localhost:5000 >nul 2>&1

REM Run the application
python run.py

pause
