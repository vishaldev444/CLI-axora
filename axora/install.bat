@echo off
REM ============================================================
REM  Axora CLI Agent — Windows Installer
REM  Usage: install.bat [--dev]
REM ============================================================
setlocal EnableDelayedExpansion

set AXORA_VERSION=1.0.0
set VENV_DIR=%USERPROFILE%\.axora\venv
set CONFIG_DIR=%USERPROFILE%\.axora
set LOG_DIR=%CONFIG_DIR%\logs
set DEV_MODE=false

REM Parse args
:parse_args
if "%1"=="--dev" set DEV_MODE=true
if "%1"=="--venv-dir" (set VENV_DIR=%2 & shift)
shift
if not "%1"=="" goto parse_args

echo.
echo     █████╗ ██╗  ██╗ ██████╗ ██████╗  █████╗
echo    ██╔══██╗╚██╗██╔╝██╔═══██╗██╔══██╗██╔══██╗
echo    ███████║ ╚███╔╝ ██║   ██║██████╔╝███████║
echo    ██╔══██║ ██╔██╗ ██║   ██║██╔══██╗██╔══██║
echo    ██║  ██║██╔╝ ██╗╚██████╔╝██║  ██║██║  ██║
echo    ╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝
echo.
echo     Axora CLI Agent v%AXORA_VERSION% Installer
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
  echo [ERROR] Python 3.10+ is required. Install from https://python.org
  exit /b 1
)
echo [OK] Python detected

REM Create dirs
if not exist "%CONFIG_DIR%" mkdir "%CONFIG_DIR%"
if not exist "%LOG_DIR%"    mkdir "%LOG_DIR%"
echo [OK] Directories created

REM Create venv
if not exist "%VENV_DIR%" (
  python -m venv "%VENV_DIR%"
  echo [OK] Virtual environment created
) else (
  echo [WARN] Virtual environment already exists — reusing
)

REM Activate
call "%VENV_DIR%\Scripts\activate.bat"

REM Upgrade pip
python -m pip install --quiet --upgrade pip wheel setuptools
echo [OK] pip upgraded

REM Install Axora
set SCRIPT_DIR=%~dp0
if "%DEV_MODE%"=="true" (
  pip install -e "%SCRIPT_DIR%[dev]"
  echo [OK] Installed in dev mode
) else (
  pip install "%SCRIPT_DIR%"
  echo [OK] Installed Axora v%AXORA_VERSION%
)

REM Add to PATH for this session
set PATH=%VENV_DIR%\Scripts;%PATH%
set AXORA_CONFIG_DIR=%CONFIG_DIR%

REM Write default config
set CFG=%CONFIG_DIR%\config.yaml
if not exist "%CFG%" (
  (
    echo server:
    echo   host: 127.0.0.1
    echo   port: 8765
    echo models: {}
    echo endpoints: {}
    echo chat:
    echo   system_prompt: "You are Axora, a helpful AI assistant."
    echo   max_history: 50
    echo paths:
    echo   log_file: %LOG_DIR%\axora.log
    echo   pid_file: %TEMP%\axora.pid
    echo logging:
    echo   level: INFO
  ) > "%CFG%"
  echo [OK] Default config written
)

REM Verify
axora --version >nul 2>&1
if errorlevel 1 (
  echo [ERROR] Installation verification failed
  exit /b 1
)
echo [OK] axora binary verified

echo.
echo ================================================
echo   Axora v%AXORA_VERSION% installed successfully!
echo ================================================
echo.
echo   Next steps:
echo   1. Run setup wizard:   axora init
echo   2. Start the agent:    axora agent start
echo   3. Chat with AI:       axora chat
echo   4. Check status:       axora status
echo.
echo   Logs: %LOG_DIR%\axora.log
echo.
pause
