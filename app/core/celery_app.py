from celery import Celery
from app.core.config import settings
import ssl

# Configure SSL for Redis if using rediss://
redis_options = {}
if settings.REDIS_URL.startswith('rediss://'):
    redis_options = {
        'broker_use_ssl': {
            'ssl_cert_reqs': ssl.CERT_REQUIRED,
            'ssl_ca_certs': None,
            'ssl_certfile': None,
            'ssl_keyfile': None
        },
        'redis_backend_use_ssl': {
            'ssl_cert_reqs': ssl.CERT_REQUIRED,
            'ssl_ca_certs': None,
            'ssl_certfile': None,
            'ssl_keyfile': None
        }
    }

celery_app = Celery(
    "broken_link_checker",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.services.crawler"]
)

# Configure Celery
celery_app.conf.update(
    **redis_options,
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
    broker_connection_retry=True,
    broker_connection_retry_on_startup=True,
    broker_connection_max_retries=100,
    broker_connection_timeout=30,
    broker_pool_limit=10,
    broker_heartbeat=10,
    broker_ping_interval=30,
    task_routes={
        'app.services.crawler.crawl_website': {'queue': 'default'},
        'app.services.crawler.check_link_with_selenium': {'queue': 'selenium'},
    },
    task_default_queue='default',
    task_default_exchange='default',
    task_default_routing_key='default',
    task_queues={
        'default': {
            'exchange': 'default',
            'routing_key': 'default',
            'queue_arguments': {'x-max-priority': 10},
        },
        'selenium': {
            'exchange': 'selenium',
            'routing_key': 'selenium',
            'queue_arguments': {'x-max-priority': 10},
        },
    },
) 