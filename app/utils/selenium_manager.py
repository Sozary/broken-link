from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException
import os
import logging
import threading
import time

class SeleniumManager:
    _instances = {}
    _lock = threading.Lock()
    _initialization_timeout = 30  # seconds

    def __new__(cls):
        pid = os.getpid()
        with cls._lock:
            if pid not in cls._instances:
                instance = super(SeleniumManager, cls).__new__(cls)
                instance._driver = None
                cls._instances[pid] = instance
            return cls._instances[pid]

    def __init__(self):
        pass

    @classmethod
    def get_instance(cls):
        instance = cls()
        if instance._driver is None or not instance._is_driver_alive():
            instance._create_new_driver()
        return instance._driver

    def _is_driver_alive(self):
        """Check if the current WebDriver instance is still alive."""
        if self._driver is None:
            return False
        try:
            # Try to get the current window handle
            self._driver.current_window_handle
            return True
        except:
            return False

    def _create_new_driver(self):
        """Create a new WebDriver instance with cleanup of old resources."""
        # Clean up old driver if it exists
        if self._driver is not None:
            try:
                self._driver.quit()
            except:
                pass
            finally:
                self._driver = None

        # Create new driver with timeout
        start_time = time.time()
        while time.time() - start_time < self._initialization_timeout:
            try:
                self._driver = self._create_driver()
                return
            except Exception as e:
                logging.warning(f"Failed to create driver: {str(e)}. Retrying...")
                if self._driver:
                    try:
                        self._driver.quit()
                    except:
                        pass
                time.sleep(1)
        
        raise TimeoutException(f"Failed to initialize WebDriver within {self._initialization_timeout} seconds")

    @classmethod
    def check_chrome_installation(cls):
        """Check if Chrome is properly installed and available."""
        try:
            import subprocess
            chrome_version = subprocess.check_output(
                ['/usr/bin/google-chrome', '--version'],
                stderr=subprocess.STDOUT
            ).decode()
            logging.info(f"Chrome version: {chrome_version.strip()}")
            return True
        except Exception as e:
            logging.error(f"Chrome check failed: {str(e)}")
            return False

    def _create_driver(self):
        """Create a new WebDriver instance."""
        logging.info(f"Initializing new WebDriver for process {os.getpid()}...")
        
        # Check Chrome installation first
        if not self.check_chrome_installation():
            raise RuntimeError("Chrome is not properly installed")
        
        options = Options()
        
        # Create unique directories for this instance
        pid = os.getpid()
        timestamp = int(time.time() * 1000)
        cache_dir = f"/home/celery/.cache/selenium/chrome-{pid}-{timestamp}"
        data_dir = f"/tmp/chrome-data/chrome-{pid}-{timestamp}"
        
        # Ensure directories exist and have correct permissions
        for directory in [cache_dir, data_dir]:
            try:
                os.makedirs(directory, mode=0o755, exist_ok=True)
                os.chmod(directory, 0o755)  # Ensure directory is readable and executable
            except Exception as e:
                logging.error(f"Failed to create directory {directory}: {e}")
                raise
        
        # Chrome options
        options.add_argument(f"--user-data-dir={data_dir}")
        options.add_argument(f"--disk-cache-dir={cache_dir}")
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-software-rasterizer")
        options.add_argument("--disable-extensions")
        options.add_argument("--window-size=1920,1080")
        
        # Additional stability options
        options.add_argument("--disable-background-networking")
        options.add_argument("--disable-background-timer-throttling")
        options.add_argument("--disable-client-side-phishing-detection")
        options.add_argument("--disable-default-apps")
        options.add_argument("--disable-hang-monitor")
        options.add_argument("--disable-popup-blocking")
        options.add_argument("--disable-prompt-on-repost")
        options.add_argument("--disable-sync")
        options.add_argument("--metrics-recording-only")
        options.add_argument("--no-first-run")
        options.add_argument("--safebrowsing-disable-auto-update")
        options.add_argument("--password-store=basic")
        
        # Privacy settings
        options.add_argument("--incognito")
        options.add_argument("--disable-blink-features=AutomationControlled")
        
        # Set user agent
        options.add_argument(f"--user-agent={self._get_user_agent()}")
        
        try:
            # Use webdriver_manager to get the correct ChromeDriver
            service = ChromeService(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=options)
            
            # Set timeouts
            driver.set_page_load_timeout(30)
            driver.set_script_timeout(30)
            driver.implicitly_wait(10)
            
            logging.info("WebDriver initialized successfully")
            return driver
            
        except Exception as e:
            logging.error(f"Failed to initialize WebDriver: {str(e)}")
            logging.error(f"Exception type: {type(e).__name__}")
            logging.error(f"Full exception details: {repr(e)}")
            # Clean up the directories
            try:
                import shutil
                shutil.rmtree(cache_dir, ignore_errors=True)
                shutil.rmtree(data_dir, ignore_errors=True)
            except Exception as cleanup_error:
                logging.error(f"Failed to clean up directories: {cleanup_error}")
            raise

    def _get_user_agent(self):
        return "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.6998.165 Safari/537.36"

    @classmethod
    def close(cls):
        pid = os.getpid()
        with cls._lock:
            if pid in cls._instances:
                instance = cls._instances[pid]
                if instance._driver is not None:
                    try:
                        logging.info(f"Closing WebDriver for process {pid}...")
                        instance._driver.quit()
                    except Exception as e:
                        logging.error(f"Error closing WebDriver: {str(e)}")
                    finally:
                        instance._driver = None
                        del cls._instances[pid]