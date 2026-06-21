@echo off
:: Set current directory to the directory of the batch file
cd /d "%~dp0"

echo ==========================================
echo        TeleControlPC Runner
echo ==========================================
echo.

:: Check if compiled executable exists in root or dist directory
if exist "TeleControlPC.exe" (
    echo [INFO] Running compiled executable (TeleControlPC.exe)...
    start "" "TeleControlPC.exe"
    goto end
)

:: Check if Python virtual environment and main.py exist
if exist ".venv\Scripts\python.exe" (
    if exist "main.py" (
        echo [INFO] Running Python application via virtual environment (.venv)...
        .venv\Scripts\python.exe main.py
        goto end
    )
)

if exist "dist\TeleControlPC.exe" (
    echo [INFO] Running compiled executable from dist (dist\TeleControlPC.exe)...
    start "" "dist\TeleControlPC.exe"
    goto end
)

:: Error handling if neither exists
echo [ERROR] Could not find executable (TeleControlPC.exe) or python virtual environment (.venv) with main.py.
echo.
echo Please make sure you have set up the virtual environment or built the executable.
echo.
pause

:end
