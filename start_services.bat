@echo off
chcp 65001 >nul
echo Starting TechDoc QA Assistant services...

cd /d "%~dp0"

rem 设置 UTF-8 编码环境变量，防止 Windows 环境乱码
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

echo Starting backend (port 8000)...
start /B .venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000

echo Waiting for backend to start...
timeout /t 5 /nobreak >nul

echo Starting frontend (port 8501)...
start /B .venv\Scripts\python.exe -m streamlit run frontend/app.py --server.port 8501 --server.headless true

echo Services started!
echo Backend: http://localhost:8000
echo Frontend: http://localhost:8501
