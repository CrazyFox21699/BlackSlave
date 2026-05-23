@echo off
setlocal
cd /d "%~dp0"
if "%~1"=="" (
  set /p QUESTION=Nhap cau hoi tracking: 
) else (
  set QUESTION=%*
)
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\run_tracking_query.ps1" -Question "%QUESTION%"
set EXITCODE=%ERRORLEVEL%
echo.
echo Query finished with exit code %EXITCODE%.
pause
exit /b %EXITCODE%
