# CrashCast

CrashCast is a FastAPI-first backend scaffold for geospatial crash-risk reporting with async processing.

## Stack
- FastAPI + PostgreSQL/PostGIS
- Redis + Celery
- AWS S3 presigned uploads
- XGBoost baseline training pipeline

## Run locally
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## API endpoints
- `GET /health`
- `POST /api/v1/auth/reporters`
- `POST /api/v1/media/presign`
- `POST /api/v1/reports`
- `GET /api/v1/risk-profile/{hashed_plate}`

## Notes
- `reports.location` uses PostGIS geometry (`POINT`, SRID 4326).
- Background jobs are defined in `app/workers/tasks.py` and use Celery.
- Baseline model training entrypoint is `ml_pipeline/train_baseline.py`.
