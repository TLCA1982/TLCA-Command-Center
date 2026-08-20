@echo off
set "ROOT=%~dp0"

start "TLCA Backend" cmd /k "cd /d "%ROOT%backend" && "%ROOT%.venv\Scripts\python.exe" -m uvicorn app.main:app --reload --host 0.0.0.0"
start "TLCA Frontend" cmd /k "cd /d "%ROOT%frontend" && npm run dev -- --host"

timeout /t 3 /nobreak >nul
start "" http://localhost:5173
