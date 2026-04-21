# CrashCast

CrashCast is a FastAPI-first backend scaffold for geospatial crash-risk reporting with async processing.

## Stack
- FastAPI + PostgreSQL/PostGIS
- Celery
- Local uploads (default) or AWS S3 presigned uploads
- XGBoost baseline training pipeline

## Run locally (API + worker)
```bash
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload
```

In another terminal:

```bash
.\.venv\Scripts\activate
celery -A app.workers.celery_app.celery_app worker -P solo -Q verification,scoring,nightly --loglevel=info
```

Local development defaults to SQLite and a filesystem Celery broker, so the API and worker can run without Redis.
Set `PLATE_HASH_PEPPER` in `.env` to a long random secret before non-local deployment.
Set `ADMIN_USERNAME` and `ADMIN_PASSWORD` in `.env` before exposing admin routes.
Celery uses the Windows-safe `solo` pool in this setup.
`MEDIA_STORAGE_MODE=local` avoids AWS credential requirements in local development.

## Web interfaces
- User UI: `GET /ui/report`
- Admin UI (HTTP Basic auth): `GET /admin`
- API docs: `GET /docs`

User UI supports:
- selecting/creating a reporter profile
- uploading image/video evidence (stored in local `uploads/` during local dev)
- submitting a report and immediately viewing report id/status/hash

Admin UI supports:
- viewing reports, users, and risk profile tables
- changing report verification status (`pending`, `verified`, `quarantined`)
- triggering risk profile recompute when status changes

## Optional ML training dependencies
```bash
pip install -r requirements-ml.txt
python ml_pipeline/train_baseline.py
```

## API endpoints
- `GET /health`
- `POST /api/v1/auth/reporters`
- `POST /api/v1/media/presign`
- `PUT /api/v1/media/local-upload/{object_key}` (local mode)
- `POST /api/v1/reports`
- `GET /api/v1/reports/{report_id}`
- `PATCH /api/v1/admin/reports/{report_id}/verification`
- `GET /api/v1/risk-profile/{hashed_plate}`

## Windows cmd curl examples
Create reporter:
```bat
curl.exe -X POST "http://127.0.0.1:8000/api/v1/auth/reporters" ^
  -H "Content-Type: application/json" ^
  -d "{\"social_graph_verified\":false}"
```

Create media upload URL:
```bat
curl.exe -X POST "http://127.0.0.1:8000/api/v1/media/presign" ^
  -H "Content-Type: application/json" ^
  -d "{\"filename\":\"incident.jpg\",\"content_type\":\"image/jpeg\"}"
```

Upload local media (use `upload_url` returned by the previous command):
```bat
curl.exe -X PUT "http://127.0.0.1:8000/api/v1/media/local-upload/reports/YOUR_OBJECT_KEY_FROM_PRESIGN" ^
  -H "Content-Type: image/jpeg" ^
  --data-binary "@incident.jpg"
```

## Notes
- `reports.location` stores a WKT `POINT(lon lat)` string in the local dev path.
- Background jobs are defined in `app/workers/tasks.py` and use Celery.
- Baseline model training entrypoint is `ml_pipeline/train_baseline.py`.
- Training expects `ml_pipeline/data/baseline_training.csv` with:
  `hour_of_day,day_of_week,road_type,weather,crash_density,reports_30d,reports_60d,reports_90d,reporter_weight,crash_within_6m`.
