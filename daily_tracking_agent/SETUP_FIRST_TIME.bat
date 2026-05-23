@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\setup_portable.ps1"
set EXITCODE=%ERRORLEVEL%
echo.
echo Setup finished with exit code %EXITCODE%.
pause
exit /b %EXITCODE%
