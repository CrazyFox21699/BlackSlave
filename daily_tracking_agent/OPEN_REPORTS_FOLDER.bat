@echo off
setlocal
cd /d "%~dp0"
if exist "reports" (
  explorer "%~dp0reports"
) else (
  mkdir "reports"
  explorer "%~dp0reports"
)
exit /b 0
