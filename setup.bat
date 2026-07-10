@echo off
REM ============================================================================
REM  Jarvis — One-click Windows setup
REM
REM  What this does:
REM    1. Creates a Python virtual environment
REM    2. Installs all dependencies from requirements.txt
REM    3. Scans your PC for apps and populates the database
REM ============================================================================

echo.
echo  ========================================
echo    Jarvis AI Assistant — Setup
echo  ========================================
echo.

REM -- Check for Python --------------------------------------------------------
where python >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Python is not installed or not in PATH.
    echo   Download Python from: https://www.python.org/downloads/
    echo   Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)

echo [INFO] Python found:
python --version
echo.

REM -- Create virtual environment ----------------------------------------------
if exist envJarvis\ (
    echo [INFO] Virtual environment already exists. Skipping creation.
) else (
    echo [INFO] Creating virtual environment...
    python -m venv envJarvis
    if %ERRORLEVEL% neq 0 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
    echo [INFO] Virtual environment created.
)
echo.

REM -- Activate and install dependencies ---------------------------------------
echo [INFO] Installing dependencies. This may take a few minutes...
call envJarvis\Scripts\activate.bat
pip install --upgrade pip >nul 2>&1
pip install -r requirements.txt
if %ERRORLEVEL% neq 0 (
    echo [WARNING] Some packages may have failed to install.
    echo           pvporcupine and pyaudio are optional.
)
echo.

REM -- Scan apps and populate database -----------------------------------------
echo [INFO] Scanning your PC for apps and websites...
python backend\scan_apps.py
if %ERRORLEVEL% neq 0 (
    echo [WARNING] App scan completed with warnings (some locations may be inaccessible).
) else (
    echo [INFO] Database populated successfully.
)
echo.

REM -- Done --------------------------------------------------------------------
echo  ========================================
echo    Setup complete!
echo.
echo    To start Jarvis:
echo      envJarvis\Scripts\activate
echo      python main.py
echo.
echo    For hot-word wake (say "Jarvis"):
echo      python run.py
echo  ========================================
echo.

pause
