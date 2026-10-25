@echo off
setlocal
title HKU Recycling Rules Helper - One-click Start
cd /d "%~dp0"

echo ============================================================
echo   HKU Recycling Rules Helper
echo   One-click start for Windows
echo ============================================================
echo.
echo  This script checks your setup, installs what is missing,
echo  then starts the app at http://127.0.0.1:5000
echo.
echo  The first run can take several minutes (it downloads a
echo  ~130 MB embedding model and builds the web app).
echo  Later runs start in a few seconds.
echo.

REM ---------- 0. Node.js present? ----------
where npm >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Node.js / npm was not found.
    echo         Install Node.js 20 or newer from https://nodejs.org
    echo         then run this script again.
    goto :fail
)

REM ---------- 1. Python virtual environment ----------
if not exist ".venv\Scripts\python.exe" goto :make_venv
echo [1/5] Python environment ....... OK
goto :check_env

:make_venv
echo [1/5] Python environment ....... MISSING, creating .venv now
where py >nul 2>nul
if errorlevel 1 (
    python -m venv .venv
) else (
    py -3 -m venv .venv
)
if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Could not create .venv. Is Python 3.11+ installed?
    goto :fail
)
echo       Installing Python packages, please wait ...
".venv\Scripts\python.exe" -m pip install --upgrade pip >nul 2>nul
".venv\Scripts\python.exe" -m pip install -r backend\requirements.txt
if errorlevel 1 goto :fail
echo       Python packages installed.

REM ---------- 2. .env ----------
:check_env
if exist ".env" goto :env_ok
echo [2/5] Configuration ............ MISSING, copying .env.example to .env
copy ".env.example" ".env" >nul
echo       Running WITHOUT an API key. Refusals, deferrals and
echo       hazardous-item answers work; normal answers will return
echo       SERVICE_UNAVAILABLE until you add a key.
echo       To enable them, open .env in Notepad and set:
echo           OPENROUTER_API_KEY=sk-or-v1-...
goto :check_store

:env_ok
echo [2/5] Configuration ............ OK

REM ---------- 3. Vector store ----------
:check_store
if exist "data\chroma\chroma.sqlite3" goto :store_ok
echo [3/5] Vector store ............. MISSING, building from corpus\ now
echo       The embedding model may be downloaded on this first run.
".venv\Scripts\python.exe" scripts\ingest.py
if errorlevel 1 goto :fail
goto :check_frontend

:store_ok
echo [3/5] Vector store ............. OK

REM ---------- 4. Frontend build ----------
:check_frontend
if exist "frontend\dist\index.html" goto :frontend_ok
echo [4/5] Web app build ............ MISSING, building now
pushd frontend
call npm install
if errorlevel 1 goto :build_failed
call npm run build
if errorlevel 1 goto :build_failed
popd
goto :start_server

:build_failed
popd
echo [ERROR] The frontend build failed. Read the messages above.
goto :fail

:frontend_ok
echo [4/5] Web app build ............ OK

REM ---------- 5. Run ----------
:start_server
echo [5/5] Starting the server at http://127.0.0.1:5000
echo.
echo   The browser opens automatically in about 15 seconds.
echo   Keep this window open while you use the app.
echo   Press Ctrl+C here to stop the server.
echo.
start "" /min cmd /c "ping -n 16 127.0.0.1 >nul & explorer http://127.0.0.1:5000"
".venv\Scripts\python.exe" -m flask --app backend.app run --port 5000

echo.
echo Server stopped.
pause
exit /b 0

:fail
echo.
echo [SETUP FAILED] Fix the problem above and run this script again.
pause
exit /b 1
