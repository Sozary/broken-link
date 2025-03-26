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

# Configure SSL for Redis
celery_app.conf.update(
    broker_use_ssl={
        'ssl_cert_reqs': None
    },
    redis_backend_use_ssl={
        'ssl_cert_reqs': None
    }
) 