from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse
from celery.result import AsyncResult
import redis
import json
import uuid
import asyncio

# Import the Celery app and task
from celery_config import celery_app
from tasks import crawl_website  # Import the Celery task

app = FastAPI()

# Configure CORS (change allowed origins to match frontend domain)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Change to ["http://localhost:3000"] for security
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Redis client for storing results
redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)


@app.post("/scan")
async def start_scan(data: dict):
    """Start a new scan task with a unique task_id."""
    url = data.get("url")
    if not url:
        return JSONResponse(status_code=400, content={"error": "URL is required"})
    
    task_id = str(uuid.uuid4())  # Generate a unique task ID
    crawl_website.apply_async(args=[task_id, url], task_id=task_id)  # Assign task_id

    return {"task_id": task_id}


@app.get("/status/{task_id}")
async def get_status(task_id: str):
    """Retrieve Celery task status from Redis and Celery."""
    task = AsyncResult(task_id, app=celery_app)

    # Fetch the Celery task metadata from Redis
    redis_key = f"celery-task-meta-{task_id}"
    task_result = redis_client.get(redis_key)

    if task_result:
        task_data = json.loads(task_result)
        return {"task_id": task_id, "status": task_data.get("status"), "result": task_data.get("result")}
    
    return {"task_id": task_id, "status": task.status}


@app.get("/results/{task_id}")
async def get_results(task_id: str):
    """Retrieve all results stored in Redis for the given task_id."""
    past_results = redis_client.lrange(task_id, 0, -1)  # Get all stored results

    if not past_results:
        return JSONResponse(content={"task_id": task_id, "results": [], "message": "No results found yet."})

    return JSONResponse(content={"task_id": task_id, "results": [json.loads(r) for r in past_results]})


@app.get("/status/stream/{task_id}")
async def status_stream(task_id: str):
    """Stream task status updates to the client using Server-Sent Events (SSE)."""
    async def event_generator():
        last_status = None

        while True:
            task = AsyncResult(task_id, app=celery_app)
            new_status = task.status

            if new_status != last_status:  # Only send updates if status changes
                last_status = new_status
                yield f"data: {json.dumps({'task_id': task_id, 'status': new_status})}\n\n"

            if new_status in ["SUCCESS", "FAILURE", "REVOKED"]:  # Stop if task is done
                break

            await asyncio.sleep(1)  # Prevent busy loop

    return EventSourceResponse(event_generator())