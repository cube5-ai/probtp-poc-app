"""
Core configuration module for the application
"""
import os
from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application configuration settings"""
    
    # API Configuration
    api_v1_prefix: str = "/api/v1"
    project_name: str = "ProBTP POC"
    version: str = "1.0.0"
    
    # Security
    secret_key: str = os.getenv("SECRET_KEY", "your-secret-key-here")
    access_token_expire_minutes: int = 30
    
    # Database
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./probtp.db")
    
    # Redis
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379")
    
    # CORS
    allowed_origins: List[str] = [
        "http://localhost:3000",  # Next.js dev server
        "http://localhost:3001",
        "https://probtp-poc-prod.web.app",
    ]
    
    # Environment
    environment: str = os.getenv("ENVIRONMENT", "development")
    debug: bool = environment == "development"
    
    class Config:
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    """Get cached application settings"""
    return Settings()
