from pydantic_settings import BaseSettings
from typing import List
import os

class Settings(BaseSettings):
    REDIS_URL: str
    CORS_ORIGINS: List[str] = ["*"]
    USER_AGENT: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36"
    PORT: int = 10000

    class Config:
        env_file = ".env"
        case_sensitive = True
        env_file_encoding = 'utf-8'

# Load settings from environment
settings = Settings() 