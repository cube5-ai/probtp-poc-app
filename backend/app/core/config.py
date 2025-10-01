"""
Core configuration module for the application
"""
import os
from functools import lru_cache

from dotenv import load_dotenv
from pydantic import ConfigDict
from pydantic_settings import BaseSettings

load_dotenv(override=True)


class Settings(BaseSettings):
    """Application configuration settings"""
    model_config = ConfigDict(extra='ignore', env_file='.env')

    # API Configuration
    api_v1_prefix: str = "/api/v1"
    project_name: str = "ProBTP POC"
    version: str = "1.0.0"

    # Security
    access_token_expire_minutes: int = 30

    # Database
    database_url: str = os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/probtp_poc")

    # Redis
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379")

    # Google Cloud Storage
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

    # Environment
    environment: str = os.getenv("ENVIRONMENT", "development")
    debug: bool = environment == "development"

    # Parsing Services Configuration
    mistral_ocr_api_key: str = os.getenv("MISTRAL_OCR_API_KEY", "")
    mistral_ocr_endpoint: str = os.getenv("MISTRAL_OCR_ENDPOINT", "https://api.mistral-ocr.com/v1")
    mistral_ocr_timeout: int = int(os.getenv("MISTRAL_OCR_TIMEOUT", "60"))
    mistral_ocr_max_file_size: int = int(os.getenv("MISTRAL_OCR_MAX_FILE_SIZE", "104857600"))  # 100MB
    # Auth type: 'api_key' (default) or 'service_account' for Vertex AI
    mistral_ocr_auth_type: str = os.getenv("MISTRAL_OCR_AUTH_TYPE", "api_key")
    # Optional model id for Vertex AI publisher model
    mistral_ocr_model_id: str = os.getenv("MISTRAL_OCR_MODEL_ID", "mistral-ocr-2505")

    def get_parsing_service_configs(self) -> dict[str, any]:
        """Get parsing service configurations"""
        from app.models.parsing_configuration import ParsingConfiguration

        configs = {}

        # Mistral OCR configuration
        if self.mistral_ocr_auth_type == "api_key" and self.mistral_ocr_api_key:
            configs["mistral_ocr"] = ParsingConfiguration(
                service_name="mistral_ocr",
                endpoint_url=self.mistral_ocr_endpoint,
                auth_type="api_key",
                credentials={"api_key": self.mistral_ocr_api_key},
                default_timeout=self.mistral_ocr_timeout,
                max_file_size=self.mistral_ocr_max_file_size,
                supported_formats=[".pdf", ".png", ".jpg", ".jpeg"]
            )
        elif self.mistral_ocr_auth_type == "service_account":
            # Vertex AI via service account (ADC). Endpoint must be the full rawPredict URL.
            creds: dict[str, any] = {"model_id": self.mistral_ocr_model_id}
            gac = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")
            if gac:
                creds["key_file_path"] = gac
            configs["mistral_ocr"] = ParsingConfiguration(
                service_name="mistral_ocr",
                endpoint_url=self.mistral_ocr_endpoint,
                auth_type="service_account",
                credentials=creds,
                default_timeout=self.mistral_ocr_timeout,
                max_file_size=self.mistral_ocr_max_file_size,
                supported_formats=[".pdf", ".png", ".jpg", ".jpeg"]
            )

        return configs


@lru_cache
def get_settings() -> Settings:
    """Get cached application settings"""
    return Settings()
