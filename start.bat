@echo off
setlocal enabledelayedexpansion

echo.
echo ============================================================
echo  CrashCast - local setup and launch
echo ============================================================

:: ── 1. Docker / services ─────────────────────────────────────
echo.
echo [1/6] Starting PostgreSQL + Redis via Docker Compose...
docker compose up -d >nul 2>&1
if %ERRORLEVEL% == 0 (
    echo       OK - containers started
    set DOCKER_OK=1
) else (
    echo       Docker not available - assuming PostgreSQL and Redis are already running
    set DOCKER_OK=0
)

:: ── 2. Python venv ────────────────────────────────────────────
echo.
echo [2/6] Setting up Python virtual environment...
if not exist ".venv\" (
    python -m venv .venv
    if %ERRORLEVEL% neq 0 (
        echo ERROR: 'python' not found. Install Python 3.11+ and add it to PATH.
        exit /b 1
    )
    echo       OK - created .venv
) else (
    echo       OK - .venv already exists
)
.venv\Scripts\python.exe -m pip install --quiet --upgrade pip

:: ── 3. Dependencies ───────────────────────────────────────────
echo.
echo [3/6] Installing dependencies (this may take a minute)...
.venv\Scripts\pip.exe install --quiet -r requirements.txt
if %ERRORLEVEL% neq 0 (
    echo ERROR: pip install failed.
    exit /b 1
)
echo       OK - dependencies installed

:: ── 4. .env file ──────────────────────────────────────────────
echo.
echo [4/6] Checking .env...
if not exist ".env" (
    if "%DOCKER_OK%"=="1" (
        set DB_URL=postgresql+psycopg://postgres:postgres@localhost:5432/crashcast
    ) else (
        set DB_URL=postgresql+psycopg://localhost:5432/crashcast
    )
    (
        echo APP_NAME=CrashCast API
        echo API_PREFIX=/api/v1
        echo DATABASE_URL=!DB_URL!
        echo REDIS_URL=redis://localhost:6379/0
        echo AWS_REGION=us-east-1
        echo S3_BUCKET=crashcast-media
        echo PLATE_HASH_PEPPER=change-me
    ) > .env
    echo       OK - created .env with local defaults
) else (
    echo       OK - .env already exists
)

:: ── 5. Wait for PostgreSQL ────────────────────────────────────
echo.
echo [5/6] Waiting for PostgreSQL...
set WAITED=0
set READY=0
:waitloop
.venv\Scripts\python.exe -c "import re,urllib.parse,psycopg; u=urllib.parse.urlparse(re.search(r'DATABASE_URL=(.*)',open('.env').read()).group(1).strip()); psycopg.connect(host=u.hostname or 'localhost',port=u.port or 5432,dbname=u.path.lstrip('/'),user=u.username or 'postgres',password=u.password or '').close()" >nul 2>&1
if %ERRORLEVEL% == 0 (
    set READY=1
    goto waitdone
)
set /a WAITED+=2
if %WAITED% geq 30 goto waitdone
echo       waiting... (%WAITED%s)
timeout /t 2 /nobreak >nul
goto waitloop
:waitdone
if "%READY%"=="1" (
    echo       OK - PostgreSQL is ready
) else (
    echo       WARNING - could not reach PostgreSQL; schema init may fail
)

:: ── 6. Init DB + launch ───────────────────────────────────────
echo.
echo [6/6] Initialising database schema...
.venv\Scripts\python.exe -c "from app.db.init_db import init_db; init_db()"
if %ERRORLEVEL% neq 0 (
    echo ERROR: database init failed. Is PostgreSQL running?
    exit /b 1
)
echo       OK - schema ready

echo.
echo ============================================================
echo  CrashCast is running
echo.
echo  Swagger UI : http://127.0.0.1:8000/docs
echo  ReDoc      : http://127.0.0.1:8000/redoc
echo  Health     : http://127.0.0.1:8000/health
echo.
echo  Press Ctrl+C to stop.
echo ============================================================
echo.

.venv\Scripts\uvicorn.exe app.main:app --reload
