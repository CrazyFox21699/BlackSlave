@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\run_daily_tracking_agent.ps1" %*
set EXITCODE=%ERRORLEVEL%
echo.
echo Daily report finished with exit code %EXITCODE%.
pause
exit /b %EXITCODE%
