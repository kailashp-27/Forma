@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Run scripts\setup.ps1 first to install the Python environment.
  pause
  exit /b 1
)
if not exist "frontend\dist\index.html" (
  echo Build the dashboard first: cd frontend then npm.cmd run build
  pause
  exit /b 1
)
set "COACH_PORT=8765"
echo Forma: http://localhost:8765
echo Keep this window open. Press Ctrl+C to stop.
".venv\Scripts\python.exe" -m backend
pause
