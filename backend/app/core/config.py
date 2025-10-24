"""
Core configuration module for the application
"""
from pathlib import Path
from functools import lru_cache
from typing import Optional

from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application configuration settings"""
    model_config = ConfigDict(
        extra='ignore', 
        env_file=Path(__file__).parent.parent.parent / '.env',
        env_file_encoding='utf-8'
    )

    # Environment
    ENVIRONMENT: str = "development"  # Pydantic will auto-read from env var
    debug: bool = False  # Will be set in __init__

    # API Configuration
    api_v1_prefix: str = "/api/v1"
    project_name: str = "ProBTP POC"
    version: str = "1.0.0"

    # Security
    access_token_expire_minutes: int = 30

    # Database - Development (uses full URL)
    DATABASE_URL: Optional[str] = None  # Pydantic will auto-read from env var
    
    # Database - Production (separate components for Cloud SQL)
    DB_USER: Optional[str] = None
    DB_PASSWORD: Optional[str] = None
    DB_NAME: Optional[str] = None
    CLOUD_SQL_CONNECTION_NAME: Optional[str] = None  # Format: project:region:instance

    # Redis
    redis_url: str = "redis://localhost:6379"

    # Firebase Storage
    upload_url_expiration_minutes: int = 15
    download_url_expiration_minutes: int = 60
    max_file_size_mb: int = 100
    firebase_storage_service_account_key: Optional[str] = None  # Path or JSON string

    # Firebase
    firebase_project_id: str = "probtp-poc-prod"

    # CORS
    allowed_origins: list[str] = [
        "http://localhost:3000",  # Next.js dev server
        "http://localhost:3001",  # Alternative dev port
        "https://probtp-poc-prod.web.app",  # Production frontend
    ]

    # Parsing Services Configuration
    mistral_ocr_api_key: str = ""
    mistral_ocr_endpoint: str = "https://api.mistral-ocr.com/v1"
    mistral_ocr_timeout: int = 60
    mistral_ocr_max_file_size: int = 104857600  # 100MB

    unstructured_api_key: str = ""
    unstructured_endpoint: str = "https://api.unstructured.io"
    unstructured_timeout: int = 120

    llamaparse_api_key: str = ""
    llamaparse_endpoint: str = "https://api.llamaindex.ai"
    llamaparse_timeout: int = 300

    def model_post_init(self, __context):
        """Initialize computed fields after Pydantic loads all values from env vars"""
        # Set debug flag based on environment
        self.debug = self.ENVIRONMENT.lower() in ["development", "dev"]

    def get_database_url(self) -> str:
        """
        Get the appropriate database URL based on environment.
        Production (Cloud Run) uses Unix socket connections, development uses TCP.
        """
        # Check if running in production (accept 'production' or 'prod', case-insensitive)
        is_production = self.ENVIRONMENT.lower() in ["production", "prod"]
        
        if is_production:
            # Build Unix socket connection for Cloud SQL
            if not all([self.DB_USER, self.DB_PASSWORD, self.DB_NAME, self.CLOUD_SQL_CONNECTION_NAME]):
                raise ValueError(
                    f"Production environment (ENVIRONMENT={self.ENVIRONMENT}) requires: "
                    f"DB_USER, DB_PASSWORD, DB_NAME, CLOUD_SQL_CONNECTION_NAME"
                )
            return (
                f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}"
                f"@/{self.DB_NAME}?host=/cloudsql/{self.CLOUD_SQL_CONNECTION_NAME}"
            )
        else:
            # Development - use DATABASE_URL or fallback to SQLite
            return self.DATABASE_URL or "sqlite:///./probtp_poc.db"


@lru_cache()
def get_settings() -> Settings:
    """Get cached application settings"""
    return Settings()