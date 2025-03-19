from celery_config import celery_app
import httpx
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import redis
import json
import asyncio
import logging
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Redis client for storing results
redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

# Global WebDriver instance
webdriver_instance = None

def get_webdriver():
    """Create or reuse a headless Chrome WebDriver instance."""
    global webdriver_instance
    if webdriver_instance is None:
        logging.info("Initializing new WebDriver...")
        options = Options()
        options.add_argument("--headless")  # ✅ Use the new headless mode
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--incognito")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36")

        service = Service(ChromeDriverManager().install())
        webdriver_instance = webdriver.Chrome(service=service, options=options)
    return webdriver_instance

def close_webdriver():
    """Close the WebDriver instance when all tasks are completed."""
    global webdriver_instance
    if webdriver_instance is not None:
        logging.info("Closing WebDriver...")
        webdriver_instance.quit()
        webdriver_instance = None

@celery_app.task(name="tasks.crawl_website")
def crawl_website(task_id, base_url):
    """Crawl a website and check for broken links with parallel requests."""
    asyncio.run(async_crawl_website(task_id, base_url))  # ✅ Run async crawler inside Celery task
    close_webdriver()  # ✅ Ensure WebDriver is closed after task completion
    return {"status": "completed"}

async def async_crawl_website(task_id, base_url):
    visited_urls = set()
    to_visit = [(normalize_url(base_url), None)]
    checked_external = set()

    async with httpx.AsyncClient(headers=get_headers(), follow_redirects=True, timeout=10) as client:
        while to_visit:
            batch = to_visit[:10]  # ✅ Process 10 URLs in parallel
            to_visit = to_visit[10:]

            # ✅ Run requests in parallel
            tasks = [fetch_and_process_url(client, task_id, url, parent, visited_urls, to_visit, checked_external, base_url) for url, parent in batch]
            await asyncio.gather(*tasks)

async def fetch_and_process_url(client, task_id, url, parent_url, visited_urls, to_visit, checked_external, base_url):
    """Fetch URL, process links, and check for broken links while logging details."""
    
    if url in visited_urls:
        return
    visited_urls.add(url)

    logging.info(f"Checking URL: {url} (Parent: {parent_url})")

    try:
        response = await client.get(url)
        status_code = response.status_code
        final_url = normalize_url(str(response.url))
        visited_urls.add(final_url)

        # ✅ Store result with parent info
        result_data = {
            "url": final_url,
            "status": status_code,
            "type": "internal",
            "parent": parent_url
        }
        redis_client.rpush(task_id, json.dumps(result_data))

        logging.info(f"Response {status_code} from {url}")

        if status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            for link in soup.find_all("a", href=True):
                abs_url = normalize_url(urljoin(base_url, link["href"]))
                netloc = urlparse(abs_url).netloc

                if netloc == urlparse(base_url).netloc:
                    if abs_url not in visited_urls:
                        to_visit.append((abs_url, url))
                else:
                    if abs_url not in checked_external:
                        checked_external.add(abs_url)
                        await check_external_link(task_id, abs_url, url)

    except httpx.HTTPStatusError as e:
        logging.error(f"HTTP Error {e.response.status_code} for {url}: {e.response.text}")
        redis_client.rpush(task_id, json.dumps({"url": url, "status": "error", "type": "internal", "parent": parent_url}))

    except httpx.RequestError as e:
        logging.error(f"Request Error for {url}: {e}")
        redis_client.rpush(task_id, json.dumps({"url": url, "status": "error", "type": "internal", "parent": parent_url}))

async def check_external_link(task_id, url, parent_url):
    """Check external links using a shared Selenium WebDriver instance."""
    
    logging.info(f"Checking external URL: {url} (Parent: {parent_url})")
    
    driver = get_webdriver()  # ✅ Get or reuse WebDriver instance

    status_code = "error"
    final_url = url

    try:
        driver.get(url)
        logging.info(f"Loaded page: {url}")
        final_url = driver.current_url  # Get final redirected URL

        # Simulate user scrolling and waiting for JavaScript to load
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        driver.implicitly_wait(5)

        # If the page loaded successfully, assume status 200
        status_code = "200 OK (Loaded)"
    
    except Exception as e:
        logging.error(f"Error fetching {url}: {e}")
    
    # Store result in Redis
    result_data = json.dumps({"url": final_url, "status": status_code, "type": "external", "parent": parent_url})
    redis_client.rpush(task_id, result_data)

def normalize_url(url):
    """Normalize URLs by removing trailing slashes and lowercasing."""
    parsed_url = urlparse(url)
    return f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}".rstrip('/').lower()

def get_headers():
    """Return headers mimicking a browser to avoid bot detection."""
    return {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "en-US,en;q=0.9",
        "Connection": "keep-alive",
        "Referer": "https://www.google.com/",
        "Upgrade-Insecure-Requests": "1",
    }
