"""
Core configuration module for the application
"""
from pathlib import Path
from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application configuration settings"""
    
    # Environment
    ENVIRONMENT: Optional[str] = "development"
    
    # Database - Development (uses full URL)
    DATABASE_URL: Optional[str] = None
    
    # Database - Production (separate components for Cloud SQL)
    DB_USER: Optional[str] = None
    DB_PASSWORD: Optional[str] = None
    DB_NAME: Optional[str] = None
    CLOUD_SQL_CONNECTION_NAME: Optional[str] = None  # Format: project:region:instance
    
    class Config:
        # Construct path to .env file relative to this config file
        # This makes it robust to where the script is run from
        env_file = Path(__file__).parent.parent.parent / '.env'
        env_file_encoding = "utf-8"
        # Allow extra fields to handle additional environment variables
        extra = "ignore"
    
    def get_database_url(self) -> str:
        """
        Get the appropriate database URL based on environment.
        Production (Cloud Run) uses Unix socket connections, development uses TCP.
        """
        if self.ENVIRONMENT == "production":
            # Build Unix socket connection for Cloud SQL
            if not all([self.DB_USER, self.DB_PASSWORD, self.DB_NAME, self.CLOUD_SQL_CONNECTION_NAME]):
                raise ValueError(
                    "Production environment requires: DB_USER, DB_PASSWORD, DB_NAME, CLOUD_SQL_CONNECTION_NAME"
                )
            return (
                f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}"
                f"@/{self.DB_NAME}?host=/cloudsql/{self.CLOUD_SQL_CONNECTION_NAME}"
            )
        else:
            # Development - use DATABASE_URL
            if not self.DATABASE_URL:
                raise ValueError("Development environment requires DATABASE_URL")
            return self.DATABASE_URL


@lru_cache()
def get_settings() -> Settings:
    """Get cached application settings"""
    return Settings()
