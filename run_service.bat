@echo off
REM Tel-Insights Service Runner for Windows
REM This script runs Tel-Insights services with proper Python path setup

if "%1"=="" (
    echo Tel-Insights Service Runner
    echo =============================
    echo.
    echo Usage: run_service.bat ^<service_name^>
    echo.
    echo Available services:
    echo   aggregator      - Telegram message aggregator
    echo   ai-analysis     - AI analysis service
    echo   smart-analysis  - Smart analysis MCP server
    echo   alerting        - Telegram bot service
    echo.
    echo Examples:
    echo   run_service.bat aggregator
    echo   run_service.bat ai-analysis
    echo   run_service.bat smart-analysis
    echo   run_service.bat alerting
    goto :eof
)

set SERVICE_NAME=%1

REM Set Python path to include src directory
set PYTHONPATH=%~dp0src;%PYTHONPATH%

echo 🚀 Starting %SERVICE_NAME% service...
echo 📂 Working directory: %~dp0
echo 🐍 Python path includes: %~dp0src
echo.

REM Run the service using the Python runner
python "%~dp0run_service.py" %SERVICE_NAME% 