from fastapi import FastAPI
from fastapi.responses import JSONResponse
from celery.result import AsyncResult
from sse_starlette.sse import EventSourceResponse
import redis
import json
import asyncio
import uuid  # ✅ Import UUID for custom task ID

# Import the Celery app and task
from celery_config import celery_app
from tasks import crawl_website  # ✅ Import the Celery task

app = FastAPI()

# Redis client for storing streaming results
redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)


@app.post("/scan")
async def start_scan(data: dict):
    """Start a new scan task with a custom UUID task_id."""
    url = data.get("url")
    if not url:
        return JSONResponse(status_code=400, content={"error": "URL is required"})
    
    task_id = str(uuid.uuid4())  # ✅ Generate UUID for task_id
    crawl_website.apply_async(args=[task_id, url], task_id=task_id)  # ✅ Pass task_id explicitly

    return {"task_id": task_id}


@app.get("/status/{task_id}")
async def get_status(task_id: str):
    """Retrieve Celery task status from Redis and Celery."""
    task = AsyncResult(task_id, app=celery_app)

    # ✅ Ensure we fetch the correct Celery-stored metadata
    redis_key = f"celery-task-meta-{task_id}"
    task_result = redis_client.get(redis_key)

    if task_result:
        task_data = json.loads(task_result)
        return {"task_id": task_id, "status": task_data.get("status"), "result": task_data.get("result")}
    
    return {"task_id": task_id, "status": task.status}


@app.get("/stream/{task_id}")
async def stream_results(task_id: str):
    """Retrieve all past results first, then stream live updates if task is still running."""
    
    # ✅ Get stored results from Redis
    past_results = redis_client.lrange(task_id, 0, -1)
    task = AsyncResult(task_id, app=celery_app)

    if task.state in ["SUCCESS", "FAILURE", "REVOKED"]:
        # ✅ If task is already finished, return all results immediately
        return JSONResponse(content={"task_id": task_id, "results": [json.loads(r) for r in past_results]})

    async def event_generator():
        """Stream new results until task is completed."""
        
        # ✅ Send past results once, don't stream them
        if past_results:
            yield f"data: {json.dumps({'stored_results': [json.loads(r) for r in past_results]})}\n\n"
            redis_client.delete(task_id)  # ✅ Clear stored results after sending

        # ✅ Start live streaming new results
        while True:
            result = redis_client.lpop(task_id)  # Get new result if available
            if result:
                yield f"data: {result}\n\n"
            
            task = AsyncResult(task_id, app=celery_app)
            if task.state in ["SUCCESS", "FAILURE", "REVOKED"]:  # ✅ Stop streaming when task completes
                break

            await asyncio.sleep(1)  # ✅ Prevent busy loop

    return EventSourceResponse(event_generator())
