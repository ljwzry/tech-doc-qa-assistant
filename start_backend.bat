@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000 > backend_out.log 2> backend_err.log
