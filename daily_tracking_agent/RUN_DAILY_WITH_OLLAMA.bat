@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\run_daily_with_ollama.ps1" %*
set EXITCODE=%ERRORLEVEL%
echo.
echo Daily Tracking Agent finished with exit code %EXITCODE%.
pause
exit /b %EXITCODE%
