from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "broken_link_checker",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.services.crawler"]
)

# Configure SSL for Redis
celery_app.conf.update(
    broker_use_ssl={
        'ssl_cert_reqs': None,
        'ssl_ca_certs': None,
        'ssl_certfile': None,
        'ssl_keyfile': None,
    },
    redis_backend_use_ssl={
        'ssl_cert_reqs': None,
        'ssl_ca_certs': None,
        'ssl_certfile': None,
        'ssl_keyfile': None,
    }
) 