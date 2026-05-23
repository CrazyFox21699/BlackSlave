@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\run_urgent_impact.ps1" %*
set EXITCODE=%ERRORLEVEL%
echo.
echo Urgent impact update finished with exit code %EXITCODE%.
pause
exit /b %EXITCODE%
