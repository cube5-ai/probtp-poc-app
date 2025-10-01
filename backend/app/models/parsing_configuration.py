"""
ParsingConfiguration model for service configuration and credentials
"""
from typing import Any, Literal

from pydantic import BaseModel, Field, HttpUrl, field_validator

AuthType = Literal["api_key", "bearer_token", "service_account"]
ParsingService = Literal["mistral_ocr", "unstructured", "llamaparse"]


class ParsingConfiguration(BaseModel):
    """
    Configuration settings and credentials for a parsing service.

    Contains all the information needed to connect to and authenticate with
    a document parsing service, including endpoint details, authentication
    credentials, and service capabilities/limits.
    """

    service_name: ParsingService = Field(
        ...,
        description="Identifier for the parsing service (mistral_ocr|unstructured|llamaparse)"
    )

    endpoint_url: HttpUrl | None = Field(
        default=None,
        description="Base URL for the parsing service API endpoint (optional if service has default)"
    )

    auth_type: AuthType = Field(
        ...,
        description="Authentication method used by the service (api_key|bearer_token|service_account)"
    )

    credentials: dict[str, Any] = Field(
        ...,
        description="Service-specific authentication credentials and configuration"
    )

    default_timeout: int = Field(
        ...,
        ge=1,
        le=600,  # 10 minutes maximum
        description="Default timeout for parsing operations in seconds (1-600)"
    )

    max_file_size: int = Field(
        ...,
        ge=1,
        le=524288000,  # 500MB maximum
        description="Maximum allowed file size in bytes (up to 500MB)"
    )

    supported_formats: list[str] = Field(
        ...,
        min_items=1,
        description="List of supported file extensions (e.g., ['.pdf', '.png', '.jpg'])"
    )

    provider_extra_params: dict[str, Any] = Field(
        default_factory=dict,
        description="Provider-specific configuration parameters for fine-grained control"
    )

    @field_validator('credentials')
    @classmethod
    def validate_credentials_for_auth_type(cls, v: dict[str, Any], info) -> dict[str, Any]:
        """
        Validate that credentials contain required fields for the specified auth_type.

        Different authentication methods require different credential fields:
        - api_key: requires 'api_key' field
        - bearer_token: requires 'token' field
        - service_account: requires 'key_file_path' or 'key_data' field
        """
        if not isinstance(v, dict):
            raise ValueError("credentials must be a dictionary")

        # Get auth_type from validation context
        auth_type = info.data.get('auth_type') if info.data else None

        if auth_type == 'api_key':
            if 'api_key' not in v or not v['api_key']:
                raise ValueError("credentials must contain 'api_key' field for api_key auth_type")

        elif auth_type == 'bearer_token':
            if 'token' not in v or not v['token']:
                raise ValueError("credentials must contain 'token' field for bearer_token auth_type")

        elif auth_type == 'service_account':
            # Allow Application Default Credentials (ADC) without explicit key material.
            # If neither key_file_path nor key_data is provided, runtime ADC will be used.
            # Accept as-is to let the adapter obtain tokens via google-auth.
            return v

        return v

    @field_validator('supported_formats')
    @classmethod
    def validate_supported_formats(cls, v: list[str]) -> list[str]:
        """
        Validate that supported_formats contains valid file extensions.

        All formats must start with a dot and be lowercase.
        Common formats should be properly formatted.
        """
        if not v:
            raise ValueError("supported_formats cannot be empty")

        validated_formats = []
        for fmt in v:
            if not isinstance(fmt, str):
                raise ValueError(f"Format '{fmt}' must be a string")

            fmt = fmt.lower().strip()
            if not fmt.startswith('.'):
                raise ValueError(f"Format '{fmt}' must start with a dot (e.g., '.pdf')")

            if len(fmt) < 2:
                raise ValueError(f"Format '{fmt}' is too short")

            validated_formats.append(fmt)

        # Remove duplicates while preserving order
        return list(dict.fromkeys(validated_formats))

    @field_validator('max_file_size')
    @classmethod
    def validate_max_file_size(cls, v: int) -> int:
        """
        Validate that max_file_size is within reasonable bounds.

        File size limits should be practical for document parsing:
        - Minimum: 1 byte (for basic validation)
        - Maximum: 500MB (to prevent resource exhaustion)
        - Common limit: 100MB as per requirements
        """
        if v < 1:
            raise ValueError("max_file_size must be at least 1 byte")

        if v > 524288000:  # 500MB
            raise ValueError("max_file_size cannot exceed 500MB (524,288,000 bytes)")

        return v

    @field_validator('default_timeout')
    @classmethod
    def validate_default_timeout(cls, v: int) -> int:
        """
        Validate that default_timeout is within reasonable bounds.

        Timeout should be sufficient for parsing operations but not excessive:
        - Minimum: 1 second
        - Maximum: 10 minutes (600 seconds)
        - Recommended: 30-300 seconds for most documents
        """
        if v < 1:
            raise ValueError("default_timeout must be at least 1 second")

        if v > 600:
            raise ValueError("default_timeout cannot exceed 600 seconds (10 minutes)")

        return v

    class Config:
        """Pydantic configuration for ParsingConfiguration model"""
        json_schema_extra = {
            "examples": [
                {
                    "service_name": "mistral_ocr",
                    "endpoint_url": None,  # Uses default Vertex AI endpoint
                    "auth_type": "service_account",
                    "credentials": {},  # Uses Application Default Credentials
                    "default_timeout": 120,
                    "max_file_size": 104857600,  # 100MB
                    "supported_formats": [".pdf", ".png", ".jpg", ".jpeg"],
                    "provider_extra_params": {
                        "region": "us-central1",
                        "project_id": "my-gcp-project",
                        "model_id": "pixtral-12b-2409"
                    }
                },
                {
                    "service_name": "unstructured",
                    "endpoint_url": "https://api.unstructured.io/general/v0/general",
                    "auth_type": "api_key",
                    "credentials": {
                        "api_key": "your-api-key-here"
                    },
                    "default_timeout": 60,
                    "max_file_size": 52428800,  # 50MB
                    "supported_formats": [".pdf", ".docx", ".html"],
                    "provider_extra_params": {
                        "strategy": "hi_res",
                        "include_page_breaks": True
                    }
                }
            ]
        }
