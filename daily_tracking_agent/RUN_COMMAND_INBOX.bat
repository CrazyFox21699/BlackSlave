@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\run_command_inbox.ps1" %*
set EXITCODE=%ERRORLEVEL%
echo.
echo Command inbox check finished with exit code %EXITCODE%.
pause
exit /b %EXITCODE%
