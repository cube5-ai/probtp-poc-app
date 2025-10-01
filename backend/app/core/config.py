"""
Core configuration module for the application
"""
from pathlib import Path
from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application configuration settings"""
    
    # Database
    DATABASE_URL: str
    
    class Config:
        # Construct path to .env file relative to this config file
        # This makes it robust to where the script is run from
        env_file = Path(__file__).parent.parent.parent / '.env'
        env_file_encoding = "utf-8"
        # Allow extra fields to handle additional environment variables
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    """Get cached application settings"""
    return Settings()
