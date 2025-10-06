"""
ParsingRequest model for input parameters to document parsing operations
"""
from typing import Any, Literal
from urllib.parse import urlparse

from pydantic import BaseModel, Field, HttpUrl, field_validator

ParsingService = Literal["mistral_ocr", "unstructured", "llamaparse"]


class ParsingRequest(BaseModel):
    """
    Input parameters for a document parsing operation.

    Contains all the information needed to initiate a parsing request,
    including the document location, service selection, timeout preferences,
    and service-specific configuration options.
    """

    file_path: str = Field(
        ...,
        min_length=1,
        description="Document URL - either GCS path (gs://bucket/path/file.ext) or HTTP(S) URL"
    )

    service_name: ParsingService = Field(
        ...,
        description="Requested parsing service (mistral_ocr|unstructured|llamaparse)"
    )

    timeout_seconds: int | None = Field(
        None,
        ge=1,
        le=600,  # 10 minutes maximum
        description="Custom timeout override in seconds (1-600), uses service default if not specified"
    )

    options: dict[str, Any] = Field(
        default_factory=dict,
        description="Service-specific parsing options and configuration parameters"
    )

    callback_url: HttpUrl | None = Field(
        None,
        description="Optional webhook URL for async completion notifications"
    )

    @field_validator('file_path')
    @classmethod
    def validate_file_path(cls, v: str) -> str:
        """
        Validate that file_path is a valid URL.

        Accepts either:
        - GCS paths: gs://bucket/path/file.ext
        - HTTP(S) URLs: https://example.com/path/file.ext

        Also validates that the file extension is supported for parsing.
        """
        if not v or not v.strip():
            raise ValueError("file_path cannot be empty")

        v = v.strip()

        # Check if it's a valid URL (GCS or HTTP/HTTPS)
        if not (v.startswith('gs://') or v.startswith('http://') or v.startswith('https://')):
            raise ValueError("file_path must be a valid URL (gs://, http://, or https://)")

        # Parse the URL to validate structure
        try:
            parsed = urlparse(v)
            if not parsed.netloc:  # domain or bucket name
                raise ValueError("file_path must include a valid domain or bucket name")
            if not parsed.path or parsed.path == '/':  # object/file path
                raise ValueError("file_path must include a valid file path")
        except Exception as e:
            raise ValueError(f"Invalid URL format: {str(e)}")

        # Validate file extension
        supported_extensions = {'.pdf', '.png', '.jpg', '.jpeg', '.tiff', '.tif', '.bmp', '.webp'}
        # Extract filename from URL path (handle query params)
        path = parsed.path.split('?')[0]
        file_ext = path.lower().split('.')[-1]
        if f'.{file_ext}' not in supported_extensions:
            raise ValueError(
                f"Unsupported file format '.{file_ext}'. "
                f"Supported formats: {', '.join(sorted(supported_extensions))}"
            )

        return v

    @field_validator('options')
    @classmethod
    def validate_options(cls, v: dict[str, Any]) -> dict[str, Any]:
        """
        Validate parsing options dictionary.

        Ensures options contains only valid key-value pairs and
        no sensitive information like API keys.
        """
        if not isinstance(v, dict):
            raise ValueError("options must be a dictionary")

        # Check for potentially sensitive keys that should not be in options
        sensitive_keys = {'api_key', 'secret', 'password', 'token', 'credentials'}
        for key in v:
            if any(sensitive in key.lower() for sensitive in sensitive_keys):
                raise ValueError(f"Sensitive key '{key}' not allowed in options")

        return v

    @field_validator('timeout_seconds')
    @classmethod
    def validate_timeout(cls, v: int | None) -> int | None:
        """
        Validate timeout is within reasonable bounds.

        Timeout must be at least 1 second and at most 10 minutes (600 seconds).
        """
        if v is not None:
            if v < 1:
                raise ValueError("timeout_seconds must be at least 1 second")
            if v > 600:
                raise ValueError("timeout_seconds cannot exceed 600 seconds (10 minutes)")

        return v

    class Config:
        """Pydantic configuration for ParsingRequest model"""
        json_schema_extra = {
            "example": {
                "file_path": "https://storage.googleapis.com/bucket/documents/sample.pdf",
                "service_name": "mistral_ocr",
                "timeout_seconds": 60,
                "options": {
                    "extract_tables": True,
                    "preserve_formatting": False,
                    "language": "en"
                },
                "callback_url": "https://myapp.example.com/webhooks/parsing-complete"
            },
            "example_gcs": {
                "file_path": "gs://parsing-bucket/documents/sample.pdf",
                "service_name": "mistral_ocr",
                "timeout_seconds": 60,
                "options": {
                    "extract_tables": True
                }
            }
        }
