"""
Core configuration module for the application
"""
import os
from pathlib import Path
from functools import lru_cache
from typing import Optional

from dotenv import load_dotenv
from pydantic import ConfigDict
from pydantic_settings import BaseSettings

load_dotenv(override=True)


class Settings(BaseSettings):
    """Application configuration settings"""
    model_config = ConfigDict(
        extra='ignore', 
        env_file=Path(__file__).parent.parent.parent / '.env',
        env_file_encoding='utf-8'
    )

    # Environment
    ENVIRONMENT: Optional[str] = "development"
    environment: str = os.getenv("ENVIRONMENT", "development")  # Keep both for compatibility
    debug: bool = environment == "development"

    # API Configuration
    api_v1_prefix: str = "/api/v1"
    project_name: str = "ProBTP POC"
    version: str = "1.0.0"

    # Security
    access_token_expire_minutes: int = 30

    # Database - Development (uses full URL)
    DATABASE_URL: Optional[str] = None
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./probtp_poc.db")  # Fallback to SQLite
    
    # Database - Production (separate components for Cloud SQL)
    DB_USER: Optional[str] = None
    DB_PASSWORD: Optional[str] = None
    DB_NAME: Optional[str] = None
    CLOUD_SQL_CONNECTION_NAME: Optional[str] = None  # Format: project:region:instance

    # Redis
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379")

    # Firebase Storage
    upload_url_expiration_minutes: int = int(os.getenv("UPLOAD_URL_EXPIRATION_MINUTES", "15"))
    download_url_expiration_minutes: int = int(os.getenv("DOWNLOAD_URL_EXPIRATION_MINUTES", "60"))
    max_file_size_mb: int = int(os.getenv("MAX_FILE_SIZE_MB", "100"))

    # Firebase
    firebase_project_id: str = os.getenv("FIREBASE_PROJECT_ID", "probtp-poc-prod")

    # CORS
    allowed_origins: list[str] = [
        "http://localhost:3000",  # Next.js dev server
        "http://localhost:3001",  # Alternative dev port
        "https://probtp-poc-prod.web.app",  # Production frontend
    ]

    # Parsing Services Configuration
    mistral_ocr_api_key: str = os.getenv("MISTRAL_OCR_API_KEY", "")
    mistral_ocr_endpoint: str = os.getenv("MISTRAL_OCR_ENDPOINT", "https://api.mistral-ocr.com/v1")
    mistral_ocr_timeout: int = int(os.getenv("MISTRAL_OCR_TIMEOUT", "60"))
    mistral_ocr_max_file_size: int = int(os.getenv("MISTRAL_OCR_MAX_FILE_SIZE", "104857600"))  # 100MB

    unstructured_api_key: str = os.getenv("UNSTRUCTURED_API_KEY", "")
    unstructured_endpoint: str = os.getenv("UNSTRUCTURED_ENDPOINT", "https://api.unstructured.io")
    unstructured_timeout: int = int(os.getenv("UNSTRUCTURED_TIMEOUT", "120"))

    llamaparse_api_key: str = os.getenv("LLAMAPARSE_API_KEY", "")
    llamaparse_endpoint: str = os.getenv("LLAMAPARSE_ENDPOINT", "https://api.llamaindex.ai")
    llamaparse_timeout: int = int(os.getenv("LLAMAPARSE_TIMEOUT", "300"))


    def get_database_url(self) -> str:
        """
        Get the appropriate database URL based on environment.
        Production (Cloud Run) uses Unix socket connections, development uses TCP.
        """
        if self.ENVIRONMENT == "production" or self.environment == "production":
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
            # Development - use DATABASE_URL or fallback to SQLite
            return self.DATABASE_URL or self.database_url


@lru_cache()
def get_settings() -> Settings:
    """Get cached application settings"""
    return Settings()