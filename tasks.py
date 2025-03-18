from celery_config import celery_app
import httpx
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import redis
import json
import asyncio

# Redis client for storing streaming results
redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

@celery_app.task(name="tasks.crawl_website")
def crawl_website(task_id, base_url):
    """Crawl a website and check for broken links with parallel requests."""
    asyncio.run(async_crawl_website(task_id, base_url))  # ✅ Run async crawler inside Celery task
    return {"status": "completed"}

async def async_crawl_website(task_id, base_url):
    visited_urls = set()
    to_visit = [(normalize_url(base_url), None)]
    checked_external = set()

    async with httpx.AsyncClient() as client:
        while to_visit:
            batch = to_visit[:10]  # ✅ Process 10 URLs in parallel
            to_visit = to_visit[10:]

            # ✅ Run requests in parallel
            tasks = [fetch_and_process_url(client, task_id, url, parent, visited_urls, to_visit, checked_external, base_url) for url, parent in batch]
            await asyncio.gather(*tasks)

async def fetch_and_process_url(client, task_id, url, parent_url, visited_urls, to_visit, checked_external, base_url):
    """Fetch URL, process links, and check for broken links."""
    if url in visited_urls:
        return
    visited_urls.add(url)

    try:
        response = await client.get(url, timeout=5, follow_redirects=True)
        status_code = response.status_code
        final_url = normalize_url(str(response.url))
        visited_urls.add(final_url)

        # ✅ Store result with parent info
        result_data = json.dumps({"url": final_url, "status": status_code, "type": "internal", "parent": parent_url})
        redis_client.rpush(task_id, result_data)

        if status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            for link in soup.find_all("a", href=True):
                abs_url = normalize_url(urljoin(base_url, link["href"]))
                netloc = urlparse(abs_url).netloc

                if netloc == urlparse(base_url).netloc:
                    # ✅ Internal link → Crawl if not visited
                    if abs_url not in visited_urls:
                        to_visit.append((abs_url, url))
                else:
                    # ✅ External link → Check once, but don't crawl
                    if abs_url not in checked_external:
                        checked_external.add(abs_url)
                        await check_external_link(client, task_id, abs_url, url)

    except Exception:
        redis_client.rpush(task_id, json.dumps({"url": url, "status": "error", "type": "internal", "parent": parent_url}))

async def check_external_link(client, task_id, url, parent_url):
    """Check external links without crawling further."""
    try:
        response = await client.get(url, timeout=5, follow_redirects=True)
        status_code = response.status_code
    except Exception:
        status_code = "error"

    # ✅ Store external link check results
    result_data = json.dumps({"url": url, "status": status_code, "type": "external", "parent": parent_url})
    redis_client.rpush(task_id, result_data)

def normalize_url(url):
    """Normalize URLs by removing trailing slashes and lowercasing."""
    parsed_url = urlparse(url)
    return f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}".rstrip('/').lower()
