#!/usr/bin/env bash
# CrashCast – full local setup and launch (macOS / Linux)
# Usage: ./start.sh
set -euo pipefail

step()  { echo; echo "==> $*"; }
ok()    { echo "    $*"; }
warn()  { echo "    [warn] $*"; }

# ── 1. Docker / services ─────────────────────────────────────────────────────
step "Starting PostgreSQL + Redis via Docker Compose"
if command -v docker &>/dev/null && docker info &>/dev/null 2>&1; then
    docker compose up -d
    DOCKER_OK=1
    ok "Containers started"
else
    warn "Docker not available – assuming PostgreSQL and Redis are already running locally"
    DOCKER_OK=0
fi

# ── 2. Python venv ───────────────────────────────────────────────────────────
step "Setting up Python virtual environment"
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
    ok "Created .venv"
else
    ok ".venv already exists"
fi
# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install --quiet --upgrade pip
ok "pip up to date"

# ── 3. Dependencies ──────────────────────────────────────────────────────────
step "Installing dependencies"
pip install --quiet -r requirements.txt
ok "Dependencies installed"

# ── 4. .env file ─────────────────────────────────────────────────────────────
step "Checking .env"
if [ ! -f ".env" ]; then
    if [ "$DOCKER_OK" -eq 1 ]; then
        DB_URL="postgresql+psycopg://postgres:postgres@localhost:5432/crashcast"
    else
        DB_URL="postgresql+psycopg://localhost:5432/crashcast"
    fi
    cat > .env <<EOF
APP_NAME=CrashCast API
API_PREFIX=/api/v1
DATABASE_URL=${DB_URL}
REDIS_URL=redis://localhost:6379/0
AWS_REGION=us-east-1
S3_BUCKET=crashcast-media
PLATE_HASH_PEPPER=change-me
EOF
    ok "Created .env with defaults (edit PLATE_HASH_PEPPER before going to production)"
else
    ok ".env already exists"
fi

# ── 5. Wait for PostgreSQL ────────────────────────────────────────────────────
step "Waiting for PostgreSQL to be ready"
MAX_WAIT=30; WAITED=0; READY=0
while [ "$WAITED" -lt "$MAX_WAIT" ]; do
    if python - <<'PY' 2>/dev/null
import re, urllib.parse, psycopg
raw = open('.env').read()
m = re.search(r'DATABASE_URL=(.*)', raw)
u = urllib.parse.urlparse(m.group(1).strip())
psycopg.connect(host=u.hostname or 'localhost', port=u.port or 5432,
                dbname=u.path.lstrip('/'), user=u.username or 'postgres',
                password=u.password or '').close()
PY
    then
        READY=1; break
    fi
    sleep 2; WAITED=$((WAITED+2))
    printf "    waiting... (%ds)\r" "$WAITED"
done
if [ "$READY" -eq 1 ]; then ok "PostgreSQL is ready"
else warn "Could not confirm PostgreSQL is up – init_db may fail"; fi

# ── 6. Init DB ────────────────────────────────────────────────────────────────
step "Initialising database schema"
python -c "from app.db.init_db import init_db; init_db()"
ok "Schema ready"

# ── 7. Launch ─────────────────────────────────────────────────────────────────
step "Starting CrashCast API"
echo
echo "  Swagger UI : http://127.0.0.1:8000/docs"
echo "  ReDoc      : http://127.0.0.1:8000/redoc"
echo "  Health     : http://127.0.0.1:8000/health"
echo
echo "  Press Ctrl+C to stop."
echo

uvicorn app.main:app --reload
