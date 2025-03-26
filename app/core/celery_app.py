from celery import Celery
from app.core.config import settings

# Add SSL parameters to Redis URL
redis_url = settings.REDIS_URL
if redis_url.startswith('rediss://'):
    redis_url = f"{redis_url}?ssl_cert_reqs=none"

celery_app = Celery(
    "broken_link_checker",
    broker=redis_url,
    backend=redis_url,
    include=["app.services.crawler"]
)

# Configure Celery
celery_app.conf.update(
    broker_use_ssl={
        'ssl_cert_reqs': None
    },
    redis_backend_use_ssl={
        'ssl_cert_reqs': None
    },
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1 hour
    task_soft_time_limit=3300,  # 55 minutes
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    result_expires=3600,  # Results expire after 1 hour
    task_routes={
        'app.services.crawler.crawl_website': {'queue': 'default'}
    }
) 