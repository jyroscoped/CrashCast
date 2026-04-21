import sys
from pathlib import Path

from celery import Celery

from app.core.config import settings


BASE_DIR = Path(__file__).resolve().parents[2]
broker_root = BASE_DIR / ".celery_broker"
broker_in = broker_root / "in"
broker_out = broker_root / "out"
broker_in.mkdir(parents=True, exist_ok=True)
broker_out.mkdir(parents=True, exist_ok=True)

celery_app = Celery("crashcast", broker=settings.celery_broker_url, backend=settings.celery_result_backend)
celery_app.conf.task_always_eager = settings.celery_always_eager
celery_app.conf.task_eager_propagates = True
celery_app.conf.worker_pool = "solo" if sys.platform.startswith("win") else "prefork"
celery_app.conf.worker_concurrency = 1
celery_app.conf.task_ignore_result = True
celery_app.conf.broker_transport_options = {
    "data_folder_in": str(broker_in),
    "data_folder_out": str(broker_out),
    "store_processed": False,
}
celery_app.conf.task_routes = {
    "app.workers.tasks.verify_media_task": {"queue": "verification"},
    "app.workers.tasks.recompute_risk_profile_task": {"queue": "scoring"},
    "app.workers.tasks.nightly_credibility_update_task": {"queue": "nightly"},
}
