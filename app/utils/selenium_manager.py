from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
import logging
import os
import threading
import subprocess

class SeleniumManager:
    _instances = {}
    _lock = threading.Lock()

    def __new__(cls):
        pid = os.getpid()
        with cls._lock:
            if pid not in cls._instances:
                instance = super(SeleniumManager, cls).__new__(cls)
                instance._driver = None
                cls._instances[pid] = instance
            return cls._instances[pid]

    @classmethod
    def check_firefox_installation(cls):
        """Check if Firefox is installed and working."""
        try:
            firefox_path = "/usr/bin/firefox"
            if not os.path.exists(firefox_path):
                raise FileNotFoundError("Firefox not found at /usr/bin/firefox")

            firefox_version = subprocess.check_output(
                [firefox_path, "--version"], stderr=subprocess.STDOUT
            ).decode()
            logging.info(f"Firefox version: {firefox_version.strip()}")
            return True
        except Exception as e:
            logging.error(f"Error checking Firefox installation: {str(e)}")
            return False

    @classmethod
    def get_instance(cls):
        instance = cls()
        if instance._driver is None:
            instance._driver = instance._create_driver()
        return instance._driver

    def _create_driver(self):
        """Create a new WebDriver instance."""
        logging.info(f"Initializing new WebDriver for process {os.getpid()}...")
        
        options = Options()
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--width=1920")
        options.add_argument("--height=1080")
        options.set_preference("dom.webdriver.enabled", False)
        options.set_preference("media.navigator.permission.disabled", True)
        options.set_preference("network.http.use-cache", False)
        
        try:
            service = Service(
                executable_path="/usr/local/bin/geckodriver",
                log_path=os.devnull
            )
            
            driver = webdriver.Firefox(
                options=options,
                service=service
            )
            
            # Set reasonable timeouts
            driver.set_page_load_timeout(60)
            driver.implicitly_wait(10)
            
            logging.info("WebDriver initialized successfully")
            return driver
            
        except Exception as e:
            logging.error(f"Failed to initialize WebDriver: {e}")
            raise

    @classmethod
    def close(cls):
        pid = os.getpid()
        with cls._lock:
            if pid in cls._instances:
                instance = cls._instances[pid]
                if instance._driver is not None:
                    try:
                        instance._driver.quit()
                    except Exception as e:
                        logging.error(f"Error closing WebDriver: {e}")
                    finally:
                        instance._driver = None
                        del cls._instances[pid]