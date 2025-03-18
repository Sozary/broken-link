from celery import Celery

celery_app = Celery(
    "broken_link_checker",
    broker="redis://localhost:6379/0",
    backend="redis://localhost:6379/0",
    include=["tasks"]  # ✅ Ensure Celery discovers tasks.py
)
