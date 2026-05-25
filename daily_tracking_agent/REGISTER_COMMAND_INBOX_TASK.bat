@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\register_command_inbox_task.ps1" -StartTime "07:30" -EndTime "19:30" -IntervalMinutes 1
set EXITCODE=%ERRORLEVEL%
echo.
echo Command inbox task registration finished with exit code %EXITCODE%.
pause
exit /b %EXITCODE%
