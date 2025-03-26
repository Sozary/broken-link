import ssl
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse
from celery.result import AsyncResult
import redis
import json
import uuid
import asyncio
import logging

from app.core.config import settings
from app.core.celery_app import celery_app
from app.api.schemas import (
    ScanRequest, ScanResponse, LinkCheckResult,
    TaskStatus, ResultsResponse
)
from app.services.crawler import crawl_website

router = APIRouter()

# Configure Redis client with SSL if needed

connection_pool = redis.ConnectionPool.from_url(
    settings.REDIS_URL,
    decode_responses=True,
    connection_class=redis.SSLConnection,
    ssl_cert_reqs=ssl.CERT_NONE
)

redis_client = redis.Redis(connection_pool=connection_pool)


@router.get("/health")
async def health_check():
    """Health check endpoint for Render."""
    try:
        # Try Redis connection but don't fail if it's not available
        try:
            redis_client.ping()
        except Exception as e:
            logging.warning(f"Redis health check failed: {str(e)}")
        
        return {"status": "healthy"}
    except Exception as e:
        logging.error(f"Health check failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    
@router.post("/scan", response_model=ScanResponse)
async def start_scan(data: ScanRequest):
    """Start a new scan task with a unique task_id."""
    task_id = str(uuid.uuid4())
    crawl_website.apply_async(args=[task_id, str(data.url)], task_id=task_id)
    return {"task_id": task_id}

@router.get("/status/{task_id}", response_model=TaskStatus)
async def get_status(task_id: str):
    """Retrieve Celery task status from Redis and Celery."""
    task = AsyncResult(task_id, app=celery_app)
    redis_key = f"celery-task-meta-{task_id}"
    task_result = redis_client.get(redis_key)

    if task_result:
        task_data = json.loads(task_result)
        return {
            "task_id": task_id,
            "status": task_data.get("status"),
            "result": task_data.get("result")
        }
    
    return {"task_id": task_id, "status": task.status}

@router.get("/results/{task_id}", response_model=ResultsResponse)
async def get_results(task_id: str):
    """Retrieve all results stored in Redis for the given task_id."""
    past_results = redis_client.lrange(task_id, 0, -1)

    if not past_results:
        return {
            "task_id": task_id,
            "results": [],
            "message": "No results found yet."
        }

    results = [json.loads(r) for r in past_results]
    return {"task_id": task_id, "results": results}

@router.get("/status/stream/{task_id}")
async def status_stream(task_id: str):
    """Stream task status updates to the client using Server-Sent Events (SSE)."""
    async def event_generator():
        last_status = None

        while True:
            task = AsyncResult(task_id, app=celery_app)
            new_status = task.status

            if new_status != last_status:
                last_status = new_status
                yield f"data: {json.dumps({'task_id': task_id, 'status': new_status})}\n\n"

            if new_status in ["SUCCESS", "FAILURE", "REVOKED"]:
                break

            await asyncio.sleep(1)

    return EventSourceResponse(event_generator())