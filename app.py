from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import concurrent.futures
import json
import os

app = FastAPI()

DOMAIN = "https://blog.infotourisme.net"
JSON_FILE = "broken_links.json"
visited_links = set()
broken_links = {}


# Allow CORS for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Change to specific domains in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def load_results():
    """Load broken links from JSON file if available."""
    global broken_links
    if os.path.exists(JSON_FILE):
        with open(JSON_FILE, "r", encoding="utf-8") as f:
            try:
                broken_links = json.load(f)
            except json.JSONDecodeError:
                broken_links = {}


def save_results():
    """Save broken links to a JSON file."""
    with open(JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(broken_links, f, indent=4, ensure_ascii=False)
    print(f"Results saved to {JSON_FILE}")


def is_internal_link(url):
    """Check if the link belongs to the same domain."""
    return urlparse(url).netloc == urlparse(DOMAIN).netloc or not urlparse(url).netloc


def is_valid_link(url):
    """Exclude mailto, javascript, and empty links."""
    return not url.startswith(("mailto:", "javascript:", "#"))


def check_link(url, referrer):
    """Check if a link is broken and store its referrer."""
    try:
        response = requests.head(url, allow_redirects=True, timeout=5)
        if response.status_code >= 400:
            print(f"[BROKEN] {url} (from {referrer}) - Status: {response.status_code}")
            if url not in broken_links:
                broken_links[url] = {"status": response.status_code, "referrers": []}
            if referrer not in broken_links[url]["referrers"]:
                broken_links[url]["referrers"].append(referrer)
    except requests.RequestException as e:
        print(f"[ERROR] {url} (from {referrer}) - Exception: {e}")
        if url not in broken_links:
            broken_links[url] = {"status": "ERROR", "referrers": []}
        if referrer not in broken_links[url]["referrers"]:
            broken_links[url]["referrers"].append(referrer)


def crawl_website(url):
    """Crawl the website recursively to find broken links."""
    if url in visited_links:
        return
    visited_links.add(url)

    try:
        response = requests.get(url, timeout=5)
        if response.status_code >= 400:
            return

        soup = BeautifulSoup(response.text, "html.parser")
        links = [a.get("href") for a in soup.find_all("a", href=True)]

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = []
            for link in links:
                full_link = urljoin(url, link)
                if is_internal_link(full_link) and is_valid_link(full_link) and full_link not in visited_links:
                    futures.append(executor.submit(check_link, full_link, url))
                    futures.append(executor.submit(crawl_website, full_link))
            concurrent.futures.wait(futures)
    except requests.RequestException:
        pass


@app.get("/")
async def index():
    """Basic route to test the API."""
    return {"message": "Broken Link Checker API is running!"}


@app.get("/data")
async def get_data():
    """Return broken links as JSON."""
    return JSONResponse(content=broken_links)


@app.get("/crawl")
async def run_crawler():
    """Trigger website crawling and return the latest results."""
    load_results()
    crawl_website(DOMAIN)
    save_results()
    return {"message": "Crawling completed", "broken_links": broken_links}


# Load existing data before starting
load_results()
crawl_website(DOMAIN)
save_results()
