from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
import os
import logging

class SeleniumManager:
    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls._create_driver()
        return cls._instance

    @classmethod
    def _create_driver(cls):
        logging.info("Initializing new WebDriver...")
        options = Options()
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--incognito")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-software-rasterizer")
        options.add_argument("--ignore-certificate-errors")
        options.add_argument("--allow-running-insecure-content")
        options.add_argument("--disable-web-security")
        options.add_argument("--disable-features=IsolateOrigins,site-per-process")
        options.add_argument("--disable-site-isolation-trials")
        
        # Use system-installed Chrome driver
        chrome_driver_path = os.getenv('CHROMEDRIVER_PATH', '/usr/bin/chromedriver')
        chrome_binary_path = os.getenv('CHROME_BIN', '/usr/bin/chromium')
        
        if not os.path.exists(chrome_driver_path):
            raise Exception(f"Chrome driver not found at {chrome_driver_path}")
            
        if not os.path.exists(chrome_binary_path):
            raise Exception(f"Chrome binary not found at {chrome_binary_path}")
            
        options.binary_location = chrome_binary_path
        service = Service(executable_path=chrome_driver_path)
        
        try:
            driver = webdriver.Chrome(service=service, options=options)
            logging.info("WebDriver initialized successfully")
            return driver
        except Exception as e:
            logging.error(f"Failed to initialize WebDriver: {str(e)}")
            raise

    @classmethod
    def close(cls):
        if cls._instance is not None:
            try:
                logging.info("Closing WebDriver...")
                cls._instance.quit()
            except Exception as e:
                logging.error(f"Error closing WebDriver: {str(e)}")
            finally:
                cls._instance = None 