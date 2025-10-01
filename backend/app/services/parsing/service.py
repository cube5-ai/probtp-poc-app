"""
Parsing service orchestrator
Manages multiple parsing service adapters and handles service selection
"""
import logging
from datetime import datetime
from typing import Any

from app.models.parsed_document import ParsedDocument
from app.models.parsing_configuration import ParsingConfiguration
from app.models.parsing_request import ParsingRequest
from app.services.parsing.adapters.base import BaseParsingAdapter
from app.services.parsing.adapters.mistral_ocr import MistralOCRAdapter

# from app.services.parsing.adapters.unstructured_io import UnstructuredIOAdapter
# from app.services.parsing.adapters.llamaparse import LlamaParseAdapter


logger = logging.getLogger(__name__)


class ParsingService:
    """
    Main parsing service that orchestrates multiple parsing adapters.

    This service manages the routing of parsing requests to appropriate
    service adapters based on the requested service name or automatic
    selection based on file type and availability.
    """

    def __init__(self, configs: dict[str, ParsingConfiguration]):
        """
        Initialize the parsing service with adapter configurations.

        Args:
            configs: Dictionary mapping service names to their configurations
        """
        self.configs = configs
        self.adapters: dict[str, BaseParsingAdapter] = {}
        self._initialize_adapters()

        logger.info(f"Initialized parsing service with {len(self.adapters)} adapters", extra={
            "services": list(self.adapters.keys())
        })

    def _initialize_adapters(self) -> None:
        """Initialize all configured parsing adapters."""
        adapter_classes = {
            "mistral_ocr": MistralOCRAdapter,
            #"unstructured": UnstructuredIOAdapter,
            #"llamaparse": LlamaParseAdapter
        }

        for service_name, config in self.configs.items():
            if service_name in adapter_classes:
                try:
                    adapter_class = adapter_classes[service_name]
                    self.adapters[service_name] = adapter_class(config)
                    logger.info(f"Initialized {service_name} adapter successfully")
                except Exception as e:
                    logger.error(f"Failed to initialize {service_name} adapter: {e}")
            else:
                logger.warning(f"Unknown service type: {service_name}")

    async def parse_document(self, request: ParsingRequest) -> ParsedDocument:
        """
        Parse a document using the specified service adapter.

        Args:
            request: Parsing request with service name and file details

        Returns:
            ParsedDocument: Parsed document with content blocks

        Raises:
            ValueError: If service is not supported or not available
        """
        correlation_id = f"parse_{hash(request.file_path)}_{int(datetime.utcnow().timestamp())}"

        logger.info("Starting document parsing", extra={
            "correlation_id": correlation_id,
            "file_path": request.file_path,
            "service": request.service_name,
            "timeout": request.timeout_seconds
        })

        # Validate service name
        if request.service_name not in self.adapters:
            available_services = list(self.adapters.keys())
            error_msg = f"Service '{request.service_name}' not supported. Available services: {available_services}"
            logger.error(error_msg, extra={"correlation_id": correlation_id})
            raise ValueError(error_msg)

        adapter = self.adapters[request.service_name]

        try:
            # Check if fallback is enabled and handle accordingly
            if request.options.get("enable_fallback", False):
                return await self._parse_with_fallback(request, correlation_id)
            else:
                return await self._parse_single_service(adapter, request, correlation_id)

        except Exception as e:
            logger.error("Document parsing failed", extra={
                "correlation_id": correlation_id,
                "service": request.service_name,
                "error": str(e)
            })
            raise

    async def _parse_single_service(
        self,
        adapter: BaseParsingAdapter,
        request: ParsingRequest,
        correlation_id: str
    ) -> ParsedDocument:
        """Parse document using a single service."""
        try:
            result = await adapter.parse_document(request)

            # Add correlation ID to metadata
            if not result.metadata:
                result.metadata = {}
            result.metadata["correlation_id"] = correlation_id

            logger.info("Document parsing completed successfully", extra={
                "correlation_id": correlation_id,
                "service": request.service_name,
                "status": result.status,
                "blocks_count": len(result.content_blocks)
            })

            return result

        except Exception as e:
            logger.error("Single service parsing failed", extra={
                "correlation_id": correlation_id,
                "service": request.service_name,
                "error": str(e)
            })
            raise

    # async def _parse_with_fallback(
    #     self,
    #     request: ParsingRequest,
    #     correlation_id: str
    # ) -> ParsedDocument:
    #     """Parse document with fallback to alternative services."""
    #     primary_service = request.service_name
    #     fallback_services = request.options.get("fallback_services", [])

    #     # Try primary service first
    #     try:
    #         adapter = self.adapters[primary_service]
    #         result = await adapter.parse_document(request)

    #         if result.status == "completed":
    #             logger.info(f"Primary service succeeded", extra={
    #                 "correlation_id": correlation_id,
    #                 "service": primary_service
    #             })
    #             return result
    #         else:
    #             logger.warning(f"Primary service failed, trying fallback", extra={
    #                 "correlation_id": correlation_id,
    #                 "primary_service": primary_service,
    #                 "status": result.status
    #             })

    #     except Exception as e:
    #         logger.warning(f"Primary service error, trying fallback", extra={
    #             "correlation_id": correlation_id,
    #             "primary_service": primary_service,
    #             "error": str(e)
    #         })

    #     # Try fallback services
    #     for fallback_service in fallback_services:
    #         if fallback_service not in self.adapters:
    #             logger.warning(f"Fallback service not available: {fallback_service}")
    #             continue

    #         try:
    #             logger.info(f"Trying fallback service", extra={
    #                 "correlation_id": correlation_id,
    #                 "fallback_service": fallback_service
    #             })

    #             # Create fallback request
    #             fallback_request = ParsingRequest(
    #                 file_path=request.file_path,
    #                 service_name=fallback_service,
    #                 timeout_seconds=request.timeout_seconds,
    #                 options=request.options
    #             )

    #             adapter = self.adapters[fallback_service]
    #             result = await adapter.parse_document(fallback_request)

    #             if result.status == "completed":
    #                 # Add fallback info to metadata
    #                 if not result.metadata:
    #                     result.metadata = {}
    #                 result.metadata["primary_service"] = primary_service
    #                 result.metadata["fallback_used"] = fallback_service
    #                 result.metadata["correlation_id"] = correlation_id

    #                 logger.info(f"Fallback service succeeded", extra={
    #                     "correlation_id": correlation_id,
    #                     "fallback_service": fallback_service
    #                 })

    #                 return result

    #         except Exception as e:
    #             logger.warning(f"Fallback service failed", extra={
    #                 "correlation_id": correlation_id,
    #                 "fallback_service": fallback_service,
    #                 "error": str(e)
    #             })
    #             continue

    #     # All services failed
    #     error_msg = f"All services failed: primary={primary_service}, fallbacks={fallback_services}"
    #     logger.error(error_msg, extra={"correlation_id": correlation_id})

    #     # Return error document from primary service
    #     adapter = self.adapters[primary_service]
    #     return adapter._create_error_document(
    #         request,
    #         "failed",
    #         "All parsing services failed"
    #     )

    async def validate_file(self, request: ParsingRequest) -> dict[str, Any]:
        """
        Validate if a file can be processed by the specified service.

        Args:
            request: Parsing request to validate

        Returns:
            Dict with validation results including file info and errors
        """
        correlation_id = f"validate_{hash(request.file_path)}_{int(datetime.utcnow().timestamp())}"

        logger.info("Starting file validation", extra={
            "correlation_id": correlation_id,
            "file_path": request.file_path,
            "service": request.service_name
        })

        result = {
            "valid": False,
            "file_size": 0,
            "format": "",
            "estimated_pages": 1,
            "errors": []
        }

        try:
            # Check if service exists
            if request.service_name not in self.adapters:
                available_services = list(self.adapters.keys())
                result["errors"].append(f"Service '{request.service_name}' not supported. Available: {available_services}")
                return result

            adapter = self.adapters[request.service_name]

            # Validate file format
            is_format_valid = await adapter.validate_file(request)
            if not is_format_valid:
                supported_formats = adapter.config.supported_formats
                result["errors"].append(f"File format not supported by {request.service_name}. Supported: {supported_formats}")

            # Extract file format
            try:
                filename = request.file_path.split("/")[-1]
                if "." in filename:
                    result["format"] = filename.split(".")[-1].lower()
                else:
                    result["errors"].append("Could not determine file format")
            except Exception:
                result["errors"].append("Invalid file path format")

            # Mock file size and pages (in real implementation, would query GCS)
            result["file_size"] = 1024000  # 1MB mock
            result["estimated_pages"] = 5  # Mock page count

            # Check file size limits
            if result["file_size"] > adapter.config.max_file_size:
                max_size_mb = adapter.config.max_file_size // (1024 * 1024)
                result["errors"].append(f"File size exceeds limit of {max_size_mb}MB for {request.service_name}")

            # File is valid if no errors
            result["valid"] = len(result["errors"]) == 0

            logger.info("File validation completed", extra={
                "correlation_id": correlation_id,
                "valid": result["valid"],
                "errors_count": len(result["errors"])
            })

            return result

        except Exception as e:
            logger.error("File validation error", extra={
                "correlation_id": correlation_id,
                "error": str(e)
            })
            result["errors"].append(f"Validation error: {str(e)}")
            return result

    async def get_available_services(self) -> list[dict[str, Any]]:
        """
        Get list of available parsing services with their status.

        Returns:
            List of service information dictionaries
        """
        services = []

        for service_name, adapter in self.adapters.items():
            try:
                # Check service health
                health = await adapter.health_check()

                service_info = {
                    "name": service_name,
                    "status": health.get("status", "unknown"),
                    "supported_formats": adapter.config.supported_formats,
                    "max_file_size": adapter.config.max_file_size,
                    "default_timeout": adapter.config.default_timeout,
                    "response_time": health.get("response_time", 0)
                }

                if "error" in health:
                    service_info["error"] = health["error"]

                services.append(service_info)

            except Exception as e:
                logger.error(f"Error checking service {service_name}: {e}")
                services.append({
                    "name": service_name,
                    "status": "unavailable",
                    "supported_formats": adapter.config.supported_formats,
                    "max_file_size": adapter.config.max_file_size,
                    "default_timeout": adapter.config.default_timeout,
                    "error": str(e)
                })

        logger.info("Retrieved service availability", extra={
            "services_count": len(services),
            "available": [s["name"] for s in services if s["status"] == "available"]
        })

        return services

    async def check_service_health(self, service_name: str) -> dict[str, Any]:
        """
        Check the health of a specific service.

        Args:
            service_name: Name of the service to check

        Returns:
            Dict with health status information

        Raises:
            ValueError: If service name is not supported
        """
        if service_name not in self.adapters:
            raise ValueError(f"Service '{service_name}' not supported")

        adapter = self.adapters[service_name]
        return await adapter.health_check()

    def get_service_config(self, service_name: str) -> ParsingConfiguration | None:
        """
        Get configuration for a specific service.

        Args:
            service_name: Name of the service

        Returns:
            Service configuration or None if not found
        """
        return self.configs.get(service_name)

    def get_supported_formats(self) -> dict[str, list[str]]:
        """
        Get supported file formats for each service.

        Returns:
            Dict mapping service names to supported format lists
        """
        formats = {}
        for service_name, adapter in self.adapters.items():
            formats[service_name] = adapter.config.supported_formats
        return formats
