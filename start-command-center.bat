@echo off
setlocal enabledelayedexpansion
set "ROOT=%~dp0"

call :CheckPort 8000
if errorlevel 1 exit /b 1

call :CheckPort 5173
if errorlevel 1 exit /b 1

start "TLCA Backend" cmd /k "cd /d "%ROOT%backend" && "%ROOT%.venv\Scripts\python.exe" -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"
start "TLCA Frontend" cmd /k "cd /d "%ROOT%frontend" && npm run dev -- --host --port 5173 --strictPort"

timeout /t 3 /nobreak >nul
start "" http://localhost:5173
exit /b 0

:CheckPort
set "PORT=%~1"
set "PORT_OWNER="
for /f "delims=" %%I in ('powershell -NoProfile -Command "$p = Get-NetTCPConnection -LocalPort %PORT% -ErrorAction SilentlyContinue; if ($p) { $proc = Get-Process -Id $p.OwningProcess -ErrorAction SilentlyContinue; if ($proc) { $proc.ProcessName + ' (PID ' + $proc.Id + ')' } else { 'PID ' + $p.OwningProcess } } else { '' }" 2^>nul') do set "PORT_OWNER=%%I"
if not defined PORT_OWNER exit /b 0

echo.
echo ERROR: Port %PORT% is already in use.
echo %PORT_OWNER%
echo Stop the existing process and rerun the launcher.
echo.
exit /b 1
