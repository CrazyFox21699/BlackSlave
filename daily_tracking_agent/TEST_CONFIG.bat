@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" main.py --config config.yaml --list-pics --dry-run
) else (
  python main.py --config config.yaml --list-pics --dry-run
)
set EXITCODE=%ERRORLEVEL%
echo.
echo Config test finished with exit code %EXITCODE%.
pause
exit /b %EXITCODE%
