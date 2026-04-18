from celery import Celery

from app.core.config import settings


celery_app = Celery("crashcast", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.task_routes = {
    "app.workers.tasks.verify_media_task": {"queue": "verification"},
    "app.workers.tasks.recompute_risk_profile_task": {"queue": "scoring"},
    "app.workers.tasks.nightly_credibility_update_task": {"queue": "nightly"},
}
