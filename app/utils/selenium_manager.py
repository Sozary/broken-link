from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
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
        
        service = Service(ChromeDriverManager().install())
        return webdriver.Chrome(service=service, options=options)

    @classmethod
    def close(cls):
        if cls._instance is not None:
            logging.info("Closing WebDriver...")
            cls._instance.quit()
            cls._instance = None 