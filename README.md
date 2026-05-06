# CrashCast

CrashCast is a FastAPI backend scaffold for geospatial crash-risk reporting with async task processing.

## What exists today

- API server for reporters, media intake, report creation, and risk-profile lookup
- Built-in server-rendered user/admin web UI (`/ui/report`, `/admin`)
- PostgreSQL/PostGIS persistence for reports and risk profiles
- Redis + Celery workers for background verification/scoring flows
- Optional S3 pre-signed media upload support
- Baseline ML training entrypoint for future risk-model work

> Current product shape: API + lightweight server-rendered UI for local testing.

## Local API UI (what you'll see on localhost)

After startup, open:

- Home UI: `http://127.0.0.1:8000/`
- User reporting UI: `http://127.0.0.1:8000/ui/report`
- Admin moderation UI: `http://127.0.0.1:8000/admin`
- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`

Swagger UI shows each endpoint grouped by tag/route, with:

- "Try it out" request forms
- JSON schema for request/response bodies
- live status codes and response payloads

### UI screenshot (localhost docs)

![CrashCast local Swagger UI](https://github.com/user-attachments/assets/f40359ba-ec38-482f-94c5-664c015e7793)

If your docs page appears blank, check browser extensions/network policy (Swagger assets are loaded from CDN by default).

## Quick start

Run one command — it handles everything (venv, dependencies, database, schema, server):

**Windows (Command Prompt or double-click)**
```bat
start.bat
```

**macOS / Linux**
```bash
chmod +x start.sh && ./start.sh
```

The script will:
1. Start PostgreSQL + Redis via Docker Compose (if Docker is running)
2. Create and populate a Python virtual environment
3. Write a `.env` file with safe local defaults if one doesn't exist yet
4. Wait until PostgreSQL accepts connections
5. Initialise the database schema
6. Launch the API at `http://127.0.0.1:8000`

> **Requires Docker Desktop** for the database step. If you already have PostgreSQL and Redis running natively, the script detects this and skips Docker.

---

## Prerequisites

- Python 3.11+
- PostgreSQL 14+ with the PostGIS extension
- Redis 6+
- (Optional) AWS credentials if testing the S3 pre-sign flow

The fastest way to get PostgreSQL and Redis running locally is with the included Docker Compose file (see below). You do **not** need Docker to run the Python API itself.

## Running the app

### Step 1 — Start PostgreSQL and Redis

**Option A: Docker Compose (recommended)**

```bash
docker compose up -d
```

This starts a PostGIS-enabled PostgreSQL instance on port 5432 and Redis on port 6379. Data is persisted in a named Docker volume between restarts.

**Option B: native installs**

Install PostgreSQL with the PostGIS extension and Redis via your OS package manager, then start both services manually.

### Step 2 — Create a Python virtual environment and install dependencies

```bash
python -m venv .venv
```

Activate it:

| Platform | Command |
|----------|---------|
| macOS / Linux | `source .venv/bin/activate` |
| Windows (PowerShell) | `.venv\Scripts\Activate.ps1` |
| Windows (cmd) | `.venv\Scripts\activate.bat` |

Then install:

```bash
pip install -r requirements.txt
```

### Step 3 — Configure environment variables

Create a `.env` file in the project root:

```env
APP_NAME=CrashCast API
API_PREFIX=/api/v1
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/crashcast
REDIS_URL=redis://localhost:6379/0
AWS_REGION=us-east-1
S3_BUCKET=crashcast-media
PLATE_HASH_PEPPER=change-me
PUBLIC_PLATE_LOOKUP_SALT=public_demo_salt_not_secret
CORS_ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
```

> If you installed PostgreSQL natively (Option B above), update `DATABASE_URL` with your actual username, password, and database name.

### Step 4 — Initialize the database schema

```bash
python -c "from app.db.init_db import init_db; init_db()"
```

### Step 5 — Start the API server

```bash
uvicorn app.main:app --reload
```

The API is now live at `http://127.0.0.1:8000`. Open `http://127.0.0.1:8000/docs` for the interactive Swagger UI.

### Step 6 — Start the Celery worker (separate terminal, optional)

Background tasks (media verification, risk-profile recomputation) run via Celery. Reports are still accepted without the worker running — tasks are queued and processed once the worker starts.

Activate the venv again in the new terminal, then:

```bash
celery -A app.workers.celery_app.celery_app worker -Q verification,scoring,nightly --loglevel=info
```

### Smoke check

```bash
curl http://127.0.0.1:8000/health
```

Expected:

```json
{"status": "ok"}
```

## Current user walkthrough (localhost)

This is the primary end-to-end flow today.

### Step 1: Create a reporter identity

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/auth/reporters" \
  -H "Content-Type: application/json" \
  -d '{"social_graph_verified": true}'
```

Save the returned `id` as `REPORTER_ID`.

### Step 2 (optional): Request a pre-signed upload URL for media

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/media/presign" \
  -H "Content-Type: application/json" \
  -d '{"filename":"incident.jpg","content_type":"image/jpeg"}'
```

### Step 3 (optional): Extract metadata from a local image

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/media/extract" \
  -F "file=@/absolute/path/to/photo.jpg"
```

This can auto-detect plate-like text, GPS, and timestamp from image metadata.

### Step 4: Submit a crash-risk behavior report

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/reports" \
  -H "Content-Type: application/json" \
  -d '{
    "reporter_id":"REPORTER_ID",
    "target_license_plate":"ABC1234",
    "behavior_category":"tailgating",
    "latitude":40.4455,
    "longitude":-79.9787,
    "reporter_latitude":40.4455,
    "reporter_longitude":-79.9787,
    "timestamp":"2026-04-20T12:34:56Z",
    "media_url":null
  }'
```

On success, a background job recomputes the target driver's risk profile.

### Step 5: Fetch the driver risk profile

The API key is `hashed_plate`, not raw plate text. Generate it with your configured `PLATE_HASH_PEPPER`:

```bash
python -c "import hmac,hashlib; print(hmac.new(b'change-me', b'ABC1234', hashlib.sha256).hexdigest())"
```

Then:

```bash
curl "http://127.0.0.1:8000/api/v1/risk-profile/HASHED_PLATE"
```

## API surface

- `GET /health`
- `POST /api/v1/auth/reporters`
- `POST /api/v1/media/presign`
- `POST /api/v1/media/extract`
- `POST /api/v1/reports`
- `GET /api/v1/reports/feed?limit=150`
- `GET /api/v1/risk-profile/{hashed_plate}`

`/api/v1/risk-profile/{hashed_plate}` now accepts either:
- internal hashed plate values produced by `PLATE_HASH_PEPPER` (HMAC-SHA256), or
- frontend lookup hashes (`sha256(PUBLIC_PLATE_LOOKUP_SALT + ":" + normalized_plate)`), which matches the localhost:3000 UI flow.

## Testing

Unit tests run without a database or Redis:

```bash
pytest -q
```

## Notes

- `reports.location` uses PostGIS geometry (`POINT`, SRID 4326).
- Background jobs are in `app/workers/tasks.py`.
- Baseline model training entrypoint: `ml_pipeline/train_baseline.py`.
- Training expects `ml_pipeline/data/baseline_training.csv` columns:
  `hour_of_day,day_of_week,road_type,weather,crash_density,reports_30d,reports_60d,reports_90d,reporter_weight,crash_within_6m`.
