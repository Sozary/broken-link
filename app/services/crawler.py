from app.core.celery_app import celery_app
import httpx
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import json
import asyncio
import logging
from app.utils.redis_client import get_redis_client
from app.utils.selenium_manager import SeleniumManager
from app.utils.url_utils import normalize_url, get_headers
import datetime

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

redis_client = get_redis_client()


def store_error(task_id, url, parent_url, error_msg, link_type="internal"):
    """Helper function to store errors in Redis."""
    error_data = {
        "url": url,
        "status": "error",
        "type": link_type,
        "parent": parent_url,
        "details": error_msg
    }
    redis_client.rpush(task_id, json.dumps(error_data))
    logging.error(f"Error stored for {url}: {error_msg}")

@celery_app.task(name="app.services.crawler.crawl_website", bind=True)
def crawl_website(self, task_id, base_url):
    """Crawl a website and check for broken links with parallel requests."""
    try:
        # Initialize task status
        self.update_state(
            state='STARTED',
            meta={
                'task_id': task_id,
                'status': 'STARTED',
                'result': None,
                'traceback': None,
                'children': [],
                'date_done': None
            }
        )

        # Verify Firefox installation before starting
        if not SeleniumManager.check_firefox_installation():
            raise RuntimeError("Firefox is not properly installed")
            
        asyncio.run(async_crawl_website(task_id, base_url))
        SeleniumManager.close()

        # Update task status to completed
        self.update_state(
            state='SUCCESS',
            meta={
                'task_id': task_id,
                'status': 'SUCCESS',
                'result': {"status": "completed"},
                'traceback': None,
                'children': [],
                'date_done': datetime.datetime.utcnow().isoformat()
            }
        )
        
        return {"status": "completed"}
    except Exception as e:
        error_msg = f"Fatal error in crawl_website task: {str(e)}"
        logging.error(error_msg)
        store_error(task_id, base_url, None, error_msg)
        
        # Update task status to failed
        self.update_state(
            state='FAILURE',
            meta={
                'task_id': task_id,
                'status': 'FAILURE',
                'result': None,
                'traceback': str(e),
                'children': [],
                'date_done': datetime.datetime.utcnow().isoformat()
            }
        )
        
        return {"status": "error", "error": str(e)}

async def async_crawl_website(task_id, base_url):
    visited_urls = set()
    to_visit = [(normalize_url(base_url), None)]
    checked_external = set()

    try:
        async with httpx.AsyncClient(headers=get_headers(), follow_redirects=True, timeout=10) as client:
            while to_visit:
                batch = to_visit[:10]  # Process 10 URLs in parallel
                to_visit = to_visit[10:]

                # Run requests in parallel
                tasks = [fetch_and_process_url(client, task_id, url, parent, visited_urls, to_visit, checked_external, base_url) 
                        for url, parent in batch]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Handle any exceptions from the gathered tasks
                for result in results:
                    if isinstance(result, Exception):
                        logging.error(f"Task failed with error: {str(result)}")
    except Exception as e:
        error_msg = f"Error in async_crawl_website: {str(e)}"
        logging.error(error_msg)
        store_error(task_id, base_url, None, error_msg)
        raise

async def fetch_and_process_url(client, task_id, url, parent_url, visited_urls, to_visit, checked_external, base_url):
    """Fetch URL, process links, and check for broken links while logging details."""
    try:
        if url in visited_urls:
            return
        visited_urls.add(url)

        logging.info(f"Checking URL: {url} (Parent: {parent_url})")

        status_code, final_url, details = await check_link(client, url)
        final_url = str(final_url)

        # Store result with parent info
        result_data = {
            "url": final_url,
            "status": status_code,
            "type": "internal",
            "parent": parent_url,
            "details": details
        }
        redis_client.rpush(task_id, json.dumps(result_data))
        logging.info(f"Response {status_code} from {url}")

        if status_code == 200:
            try:
                response = await client.get(url)
                soup = BeautifulSoup(response.text, "html.parser")
                for link in soup.find_all("a", href=True):
                    try:
                        abs_url = normalize_url(urljoin(base_url, link["href"]))
                        netloc = urlparse(abs_url).netloc

                        if netloc == urlparse(base_url).netloc:
                            if abs_url not in visited_urls:
                                to_visit.append((abs_url, url))
                        else:
                            if abs_url not in checked_external:
                                checked_external.add(abs_url)
                                await check_external_link(task_id, abs_url, url)
                    except Exception as e:
                        error_msg = f"Error processing link {link.get('href', 'unknown')}: {str(e)}"
                        store_error(task_id, link.get('href', 'unknown'), url, error_msg)
            except Exception as e:
                error_msg = f"Error processing HTML from {url}: {str(e)}"
                store_error(task_id, url, parent_url, error_msg)
    except Exception as e:
        error_msg = f"Error in fetch_and_process_url for {url}: {str(e)}"
        store_error(task_id, url, parent_url, error_msg)
        raise

async def check_link(client, url):
    """Try checking the link with HEAD, then GET, and finally Selenium if needed."""
    try:
        headers = get_headers()
        response = await client.head(url, headers=headers, follow_redirects=True)
        logging.info(f"HTTP Request: HEAD {url} -> {response.status_code}")

        if response.status_code not in [400, 403, 405]:
            return response.status_code, str(response.url), "Checked with HEAD"

        logging.warning(f"HEAD failed for {url}, falling back to GET...")
        response = await client.get(url, headers=headers, follow_redirects=True)
        logging.info(f"HTTP Request: GET {url} -> {response.status_code}")

        if response.status_code in [400, 403, 405]:
            logging.warning(f"GET also failed for {url}, falling back to Selenium...")
            return await check_link_with_selenium(url)

        return response.status_code, str(response.url), "Checked with GET"

    except Exception as e:
        logging.error(f"HTTP request failed for {url}: {e}")
        return await check_link_with_selenium(url)

async def check_link_with_selenium(url):
    """Check links using Selenium as a last resort."""
    logging.info(f"Checking URL with Selenium: {url}")
    
    status_code = "error"
    final_url = url
    details = "Unknown error"

    try:
        driver = SeleniumManager.get_instance()
        driver.get(url)
        await asyncio.sleep(3)  # Give more time for the page to load
        
        final_url = driver.current_url
        status_code = 200 if driver.current_url else "error"
        details = "Page loaded successfully" if status_code == 200 else "Failed to load page"
        
        logging.info(f"Selenium check completed for {url} -> {status_code}")
        return status_code, str(final_url), details

    except Exception as e:
        error_msg = f"Selenium error for {url}: {str(e)}"
        logging.error(error_msg)
        return "error", str(url), error_msg

async def check_external_link(task_id, url, parent_url):
    """Check external links using all available methods."""
    try:
        logging.info(f"Checking external URL: {url} (Parent: {parent_url})")
        status_code, final_url, details = await check_link(httpx.AsyncClient(), url)
        final_url = str(final_url)

        result_data = {
            "url": final_url,
            "status": status_code,
            "type": "external",
            "parent": parent_url,
            "details": details
        }
        redis_client.rpush(task_id, json.dumps(result_data))
    except Exception as e:
        error_msg = f"Error checking external link {url}: {str(e)}"
        store_error(task_id, url, parent_url, error_msg, "external")
        raise
