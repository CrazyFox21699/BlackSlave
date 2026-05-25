@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\register_windows_task.ps1" -StartTime "08:00"
set EXITCODE=%ERRORLEVEL%
echo.
echo Daily 08:00 task registration finished with exit code %EXITCODE%.
pause
exit /b %EXITCODE%
