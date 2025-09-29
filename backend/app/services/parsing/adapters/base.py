"""
Base adapter for parsing services
Defines the common interface for all parsing service adapters
"""
import logging
from abc import ABC, abstractmethod
from typing import Any

import google.auth
from google.auth.transport.requests import Request as GoogleAuthRequest

from app.models.parsed_document import ParsedDocument
from app.models.parsing_configuration import ParsingConfiguration
from app.models.parsing_request import ParsingRequest

logger = logging.getLogger(__name__)


class BaseParsingAdapter(ABC):
    """
    Abstract base class for all parsing service adapters.

    Each concrete adapter must implement the parse_document method
    and should follow the error handling and validation patterns
    defined in this base class.
    """

    def __init__(self, config: ParsingConfiguration):
        """
        Initialize the adapter with service configuration.

        Args:
            config: Service-specific configuration including credentials,
                   endpoints, and limits
        """
        self.config = config
        self.service_name = config.service_name
        self._validate_config()

        logger.info(f"Initialized {self.service_name} adapter", extra={
            "service": self.service_name,
            "endpoint": config.endpoint_url,
            "max_file_size": config.max_file_size
        })

    def _validate_config(self) -> None:
        """
        Validate the configuration for this adapter.

        Raises:
            ValueError: If configuration is invalid
        """
        if not self.config.endpoint_url:
            raise ValueError(f"Missing endpoint_url for {self.service_name}")

        # Credentials may be empty for service_account when using ADC
        if not self.config.credentials and self.config.auth_type != "service_account":
            raise ValueError(f"Missing credentials for {self.service_name}")

        if self.config.auth_type == "api_key" and "api_key" not in self.config.credentials:
            raise ValueError(f"Missing api_key in credentials for {self.service_name}")

    @abstractmethod
    async def parse_document(self, request: ParsingRequest) -> ParsedDocument:
        """
        Parse a document using the specific service implementation.

        Args:
            request: Parsing request containing file path, service name,
                    and optional parameters

        Returns:
            ParsedDocument: Standardized parsing result with content blocks

        Raises:
            ValueError: For invalid requests or unsupported formats
            TimeoutError: When parsing exceeds timeout limits
            Exception: For service-specific errors
        """
        pass

    async def validate_file(self, request: ParsingRequest) -> bool:
        """
        Validate if a file can be processed by this service.

        Args:
            request: Parsing request to validate

        Returns:
            bool: True if file can be processed, False otherwise
        """
        try:
            from urllib.parse import urlparse

            # Extract file extension from URL or path
            file_path = request.file_path.lower()

            # Parse the URL to get the path component
            if file_path.startswith(("gs://", "http://", "https://")):
                parsed_url = urlparse(file_path)
                # Get the path, remove query params if present
                path = parsed_url.path.split('?')[0]
                # Extract filename from path
                filename = path.split("/")[-1]
            else:
                # Fallback for other path formats
                filename = file_path.split("/")[-1]

            # Extract extension
            if "." not in filename:
                return False
            extension = "." + filename.split(".")[-1]

            # Check if format is supported
            return extension in self.config.supported_formats

        except Exception as e:
            logger.error(f"File validation error for {request.file_path}: {e}")
            return False

    def _get_auth_headers(self) -> dict[str, str]:
        """
        Get authentication headers for API requests.

        Returns:
            Dict[str, str]: Headers dictionary with authentication
        """
        headers = {"Content-Type": "application/json"}

        if self.config.auth_type == "api_key":
            api_key = self.config.credentials.get("api_key")
            if api_key:
                # Different services use different header names
                if self.service_name == "mistral_ocr":
                    headers["X-API-Key"] = api_key
                else:
                    headers["Authorization"] = f"Bearer {api_key}"

        elif self.config.auth_type == "bearer_token":
            # Support both 'token' (preferred) and legacy 'bearer_token'
            token = self.config.credentials.get("token") or self.config.credentials.get("bearer_token")
            if token:
                headers["Authorization"] = f"Bearer {token}"

        elif self.config.auth_type == "service_account":
            # Use Application Default Credentials to obtain an OAuth access token
            try:
                credentials, _ = google.auth.default(scopes=[
                    "https://www.googleapis.com/auth/cloud-platform",
                ])
                auth_request = GoogleAuthRequest()
                credentials.refresh(auth_request)
                if credentials.token:
                    headers["Authorization"] = f"Bearer {credentials.token}"
            except Exception as e:
                logger.error(f"Service account auth failed: {e}")

        return headers

    def _get_timeout(self, request: ParsingRequest) -> int:
        """
        Get the appropriate timeout for a request.

        Args:
            request: Parsing request

        Returns:
            int: Timeout in seconds
        """
        if request.timeout_seconds:
            return min(request.timeout_seconds, self.config.default_timeout)
        return self.config.default_timeout

    def _create_error_document(
        self,
        request: ParsingRequest,
        status: str,
        error_message: str
    ) -> ParsedDocument:
        """
        Create a ParsedDocument for error cases.

        Args:
            request: Original parsing request
            status: Error status (failed, timeout, etc.)
            error_message: Human-readable error description

        Returns:
            ParsedDocument: Error document with no content blocks
        """
        from datetime import datetime

        return ParsedDocument(
            document_id=f"error_{hash(request.file_path)}",
            source_file_path=request.file_path,
            parsing_service=self.service_name,
            status=status,
            created_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
            content_blocks=[],
            error_message=error_message,
            metadata={
                "service": self.service_name,
                "request_timeout": request.timeout_seconds,
                "error_type": status
            }
        )

    def _normalize_coordinates(
        self,
        coords: list[tuple],
        page_width: float = 612.0,
        page_height: float = 792.0
    ) -> dict[str, float]:
        """
        Normalize coordinates to 0.0-1.0 range.

        Args:
            coords: List of (x, y) coordinate tuples
            page_width: Page width in points (default PDF standard)
            page_height: Page height in points (default PDF standard)

        Returns:
            Dict with normalized x, y, width, height
        """
        if not coords or len(coords) < 2:
            return {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0}

        try:
            # Get min/max coordinates
            x_coords = [coord[0] for coord in coords]
            y_coords = [coord[1] for coord in coords]

            min_x = min(x_coords)
            max_x = max(x_coords)
            min_y = min(y_coords)
            max_y = max(y_coords)

            # Normalize to 0.0-1.0
            normalized_x = min_x / page_width
            normalized_y = min_y / page_height
            normalized_width = (max_x - min_x) / page_width
            normalized_height = (max_y - min_y) / page_height

            # Ensure bounds
            return {
                "x": max(0.0, min(1.0, normalized_x)),
                "y": max(0.0, min(1.0, normalized_y)),
                "width": max(0.0, min(1.0, normalized_width)),
                "height": max(0.0, min(1.0, normalized_height))
            }

        except Exception as e:
            logger.warning(f"Coordinate normalization failed: {e}")
            return {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0}

    async def health_check(self) -> dict[str, Any]:
        """
        Check the health/availability of the parsing service.

        Returns:
            Dict with status and response time information
        """
        import time

        import httpx

        start_time = time.time()

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Most services have a health or status endpoint
                # Convert HttpUrl to string before calling rstrip
                endpoint_str = str(self.config.endpoint_url)
                health_url = f"{endpoint_str.rstrip('/')}/health"
                response = await client.get(health_url, headers=self._get_auth_headers())

                response_time = (time.time() - start_time) * 1000  # ms

                return {
                    "status": "available" if response.status_code == 200 else "degraded",
                    "response_time": response_time,
                    "endpoint": health_url
                }

        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            logger.warning(f"Health check failed for {self.service_name}: {e}")

            return {
                "status": "unavailable",
                "response_time": response_time,
                "error": str(e)
            }


class ParsingAdapterError(Exception):
    """Base exception class for parsing adapter errors."""
    pass


class ServiceUnavailableError(ParsingAdapterError):
    """Raised when a parsing service is unavailable."""
    pass


class UnsupportedFormatError(ParsingAdapterError):
    """Raised when a file format is not supported by the service."""
    pass


class AuthenticationError(ParsingAdapterError):
    """Raised when service authentication fails."""
    pass

