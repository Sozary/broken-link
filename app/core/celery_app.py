from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "broken_link_checker",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.services.crawler"]
) 