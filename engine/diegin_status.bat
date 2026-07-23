@echo off
echo ========== Diegin Status ==========
"%~dp0..\bin\.venv\Scripts\python.exe" "%~dp0diegin_status.py"
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Failed to run diegin_status.py
    pause
)
