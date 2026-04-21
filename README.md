# CrashCast

CrashCast is a FastAPI backend scaffold for geospatial crash-risk reporting with async task processing.

## What exists today

- API server for reporters, media intake, report creation, and risk-profile lookup
- PostgreSQL/PostGIS persistence for reports and risk profiles
- Redis + Celery workers for background verification/scoring flows
- Optional S3 pre-signed media upload support
- Baseline ML training entrypoint for future risk-model work

> Current product shape: backend-first. There is no custom frontend yet; the main local UI is FastAPI's auto-generated API docs.

## Local API UI (what you'll see on localhost)

After startup, open:

- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`

Swagger UI shows each endpoint grouped by tag/route, with:

- "Try it out" request forms
- JSON schema for request/response bodies
- live status codes and response payloads

### UI screenshot (localhost docs)

![CrashCast local Swagger UI](https://github.com/user-attachments/assets/f40359ba-ec38-482f-94c5-664c015e7793)

If your docs page appears blank, check browser extensions/network policy (Swagger assets are loaded from CDN by default).

## Prerequisites

- Python 3.12+
- PostgreSQL with PostGIS enabled
- Redis
- (Optional) AWS credentials if testing real S3 presign flow

## Setup (localhost)

### 1) Create environment and install dependencies

```bash
cd <your-local-path>/CrashCast
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2) Configure environment variables

Create `.env` in the project root:

```env
APP_NAME=CrashCast API
API_PREFIX=/api/v1
DATABASE_URL=postgresql+psycopg://localhost:5432/crashcast
REDIS_URL=redis://localhost:6379/0
AWS_REGION=us-east-1
S3_BUCKET=crashcast-media
PLATE_HASH_PEPPER=change-me
```

### 3) Initialize database tables

```bash
cd <your-local-path>/CrashCast
python -c "from app.db.init_db import init_db; init_db()"
```

### 4) Start the API

```bash
cd <your-local-path>/CrashCast
source .venv/bin/activate
uvicorn app.main:app --reload
```

### 5) Start Celery worker (separate terminal)

```bash
cd <your-local-path>/CrashCast
source .venv/bin/activate
celery -A app.workers.celery_app.celery_app worker -Q verification,scoring,nightly --loglevel=info
```

### 6) Smoke check

```bash
curl http://127.0.0.1:8000/health
```

Expected:

```json
{"status":"ok"}
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
- `GET /api/v1/risk-profile/{hashed_plate}`

## Testing

```bash
cd <your-local-path>/CrashCast
source .venv/bin/activate
pytest -q
```

## Notes

- `reports.location` uses PostGIS geometry (`POINT`, SRID 4326).
- Background jobs are in `app/workers/tasks.py`.
- Baseline model training entrypoint: `ml_pipeline/train_baseline.py`.
- Training expects `ml_pipeline/data/baseline_training.csv` columns:
  `hour_of_day,day_of_week,road_type,weather,crash_density,reports_30d,reports_60d,reports_90d,reporter_weight,crash_within_6m`.
