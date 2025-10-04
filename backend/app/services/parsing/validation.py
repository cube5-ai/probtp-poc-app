"""
File validation service for parsing operations
Validates files before sending to external parsing services
"""
import logging
from typing import Any
from urllib.parse import urlparse

from app.models.parsing_configuration import ParsingConfiguration
from app.models.parsing_request import ParsingRequest

logger = logging.getLogger(__name__)


class FileValidationService:
    """
    Service for validating files before parsing operations.

    Handles validation of file paths, formats, sizes, and other
    constraints before files are sent to external parsing services.
    """

    # Supported file extensions mapped to MIME types
    SUPPORTED_EXTENSIONS = {
        ".pdf": "application/pdf",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".tiff": "image/tiff",
        ".tif": "image/tiff",
        ".bmp": "image/bmp",
        ".webp": "image/webp",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".doc": "application/msword",
        ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        ".ppt": "application/vnd.ms-powerpoint",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".xls": "application/vnd.ms-excel",
        ".txt": "text/plain",
        ".html": "text/html",
        ".htm": "text/html"
    }

    # Maximum file sizes by type (in bytes)
    DEFAULT_MAX_SIZES = {
        ".pdf": 200 * 1024 * 1024,    # 200MB
        ".png": 50 * 1024 * 1024,     # 50MB
        ".jpg": 50 * 1024 * 1024,     # 50MB
        ".jpeg": 50 * 1024 * 1024,    # 50MB
        ".tiff": 100 * 1024 * 1024,   # 100MB
        ".docx": 100 * 1024 * 1024,   # 100MB
        ".txt": 10 * 1024 * 1024,     # 10MB
        ".html": 10 * 1024 * 1024,    # 10MB
    }

    def __init__(self):
        """Initialize the file validation service."""
        # logger.info("Initialized file validation service")

    async def validate_file(
        self,
        request: ParsingRequest,
        config: ParsingConfiguration
    ) -> dict[str, Any]:
        """
        Comprehensive file validation for parsing requests.

        Args:
            request: Parsing request containing file details
            config: Configuration for the target parsing service

        Returns:
            Dict containing validation results:
            - valid: bool - whether file passes all validations
            - file_size: int - file size in bytes
            - format: str - detected file format
            - estimated_pages: int - estimated page count
            - errors: List[str] - validation error messages
            - warnings: List[str] - non-blocking warnings
        """
        result = {
            "valid": False,
            "file_size": 0,
            "format": "",
            "estimated_pages": 1,
            "errors": [],
            "warnings": []
        }

        try:
            # Step 1: Validate file path format
            path_validation = self._validate_file_path(request.file_path)
            if not path_validation["valid"]:
                result["errors"].extend(path_validation["errors"])

            # Step 2: Extract and validate file format
            format_validation = self._validate_file_format(
                request.file_path,
                config.supported_formats
            )
            result["format"] = format_validation["format"]
            if not format_validation["valid"]:
                result["errors"].extend(format_validation["errors"])

            # Step 3: Get file metadata (size, pages estimate)
            metadata = await self._get_file_metadata(request.file_path)
            result["file_size"] = metadata["size"]
            result["estimated_pages"] = metadata["estimated_pages"]

            # Step 4: Validate file size constraints
            size_validation = self._validate_file_size(
                result["file_size"],
                result["format"],
                config.max_file_size
            )
            if not size_validation["valid"]:
                result["errors"].extend(size_validation["errors"])
            result["warnings"].extend(size_validation["warnings"])

            # Step 5: Service-specific validations
            service_validation = self._validate_service_constraints(
                request,
                config,
                result["format"],
                result["file_size"]
            )
            if not service_validation["valid"]:
                result["errors"].extend(service_validation["errors"])
            result["warnings"].extend(service_validation["warnings"])

            # Overall validation result
            result["valid"] = len(result["errors"]) == 0

            # logger.info("File validation completed", extra={
            #     "file_path": request.file_path,
            #     "service": config.service_name,
            #     "valid": result["valid"],
            #     "file_size": result["file_size"],
            #     "format": result["format"],
            #     "errors_count": len(result["errors"])
            # })

            return result

        except Exception as e:
            logger.error(f"File validation error: {e}", extra={
                "file_path": request.file_path,
                "service": config.service_name
            })
            result["errors"].append(f"Validation failed: {str(e)}")
            return result

    def _validate_file_path(self, file_path: str) -> dict[str, Any]:
        """Validate the file path format."""
        result = {"valid": True, "errors": []}

        if not file_path:
            result["valid"] = False
            result["errors"].append("File path is required")
            return result

        try:
            # Check if it's a GCP storage path
            if file_path.startswith("gs://"):
                parsed = urlparse(file_path)

                # Validate bucket and object path
                if not parsed.netloc:
                    result["valid"] = False
                    result["errors"].append("Invalid GCS bucket name")

                if not parsed.path or parsed.path == "/":
                    result["valid"] = False
                    result["errors"].append("Missing GCS object path")

                # Validate path characters
                if any(char in file_path for char in ["<", ">", "\"", "|", "?", "*"]):
                    result["valid"] = False
                    result["errors"].append("File path contains invalid characters")

            else:
                result["valid"] = False
                result["errors"].append("Only GCS paths (gs://) are supported")

        except Exception as e:
            result["valid"] = False
            result["errors"].append(f"Invalid file path format: {str(e)}")

        return result

    def _validate_file_format(
        self,
        file_path: str,
        supported_formats: list[str]
    ) -> dict[str, Any]:
        """Validate file format and extension."""
        result = {"valid": True, "format": "", "errors": []}

        try:
            # Extract file extension
            filename = file_path.split("/")[-1]
            if "." not in filename:
                result["valid"] = False
                result["errors"].append("File has no extension")
                return result

            extension = "." + filename.split(".")[-1].lower()
            result["format"] = extension[1:]  # Remove the dot for format

            # Check if extension is recognized
            if extension not in self.SUPPORTED_EXTENSIONS:
                result["valid"] = False
                result["errors"].append(f"Unsupported file format: {extension}")
                return result

            # Check if service supports this format
            if extension not in supported_formats:
                result["valid"] = False
                result["errors"].append(
                    f"File format {extension} not supported by this service. "
                    f"Supported formats: {supported_formats}"
                )

        except Exception as e:
            result["valid"] = False
            result["errors"].append(f"Format validation error: {str(e)}")

        return result

    async def _get_file_metadata(self, file_path: str) -> dict[str, Any]:
        """Get file metadata including size and estimated pages."""
        metadata = {
            "size": 0,
            "estimated_pages": 1,
            "mime_type": "",
            "last_modified": None
        }

        try:
            # In a real implementation, this would query GCS
            # For now, provide reasonable mock data based on file type
            extension = "." + file_path.split(".")[-1].lower()

            # Mock file sizes based on format
            mock_sizes = {
                ".pdf": 2048000,      # 2MB
                ".png": 512000,       # 512KB
                ".jpg": 256000,       # 256KB
                ".jpeg": 256000,      # 256KB
                ".docx": 1024000,     # 1MB
                ".txt": 50000,        # 50KB
                ".html": 100000       # 100KB
            }

            metadata["size"] = mock_sizes.get(extension, 1024000)  # Default 1MB
            metadata["mime_type"] = self.SUPPORTED_EXTENSIONS.get(extension, "")

            # Estimate pages based on file size and type
            if extension == ".pdf":
                # Assume ~100KB per PDF page on average
                metadata["estimated_pages"] = max(1, metadata["size"] // 100000)
            elif extension in [".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".webp"]:
                # Images are single page
                metadata["estimated_pages"] = 1
            elif extension in [".docx", ".doc"]:
                # Assume ~50KB per document page
                metadata["estimated_pages"] = max(1, metadata["size"] // 50000)
            elif extension in [".txt", ".html"]:
                # Assume ~5KB per text page
                metadata["estimated_pages"] = max(1, metadata["size"] // 5000)
            else:
                metadata["estimated_pages"] = 1

            # Cap estimated pages at reasonable limit
            metadata["estimated_pages"] = min(metadata["estimated_pages"], 1000)

        except Exception as e:
            logger.warning(f"Could not get file metadata for {file_path}: {e}")

        return metadata

    def _validate_file_size(
        self,
        file_size: int,
        file_format: str,
        service_max_size: int
    ) -> dict[str, Any]:
        """Validate file size constraints."""
        result = {"valid": True, "errors": [], "warnings": []}

        if file_size <= 0:
            result["valid"] = False
            result["errors"].append("Invalid file size")
            return result

        # Check service-specific limit
        if file_size > service_max_size:
            size_mb = service_max_size // (1024 * 1024)
            result["valid"] = False
            result["errors"].append(f"File size ({file_size} bytes) exceeds service limit of {size_mb}MB")

        # Check format-specific recommended limits
        extension = f".{file_format}"
        if extension in self.DEFAULT_MAX_SIZES:
            recommended_size = self.DEFAULT_MAX_SIZES[extension]
            if file_size > recommended_size:
                rec_mb = recommended_size // (1024 * 1024)
                result["warnings"].append(f"File size exceeds recommended limit of {rec_mb}MB for {extension} files")

        # Warn about very large files that might timeout
        if file_size > 50 * 1024 * 1024:  # 50MB
            result["warnings"].append("Large file detected - parsing may take longer than usual")

        return result

    def _validate_service_constraints(
        self,
        request: ParsingRequest,
        config: ParsingConfiguration,
        file_format: str,
        file_size: int
    ) -> dict[str, Any]:
        """Validate service-specific constraints."""
        result = {"valid": True, "errors": [], "warnings": []}

        try:
            # Service-specific format validations
            if config.service_name == "mistral_ocr":
                # Mistral OCR is optimized for images and PDFs
                if file_format not in ["pdf", "png", "jpg", "jpeg"]:
                    result["warnings"].append("Mistral OCR works best with PDF and image formats")

            elif config.service_name == "unstructured":
                # Unstructured.io handles various document types
                if file_format in ["jpg", "jpeg", "png", "tiff", "bmp"]:
                    result["warnings"].append("Unstructured.io may have limited OCR capabilities for images")

            elif config.service_name == "llamaparse":
                # LlamaParse is optimized for complex documents
                if file_format in ["txt", "html"]:
                    result["warnings"].append("LlamaParse is optimized for complex layouts - simple text may be overkill")

            # Timeout validation based on file size and service
            if request.timeout_seconds:
                estimated_time = self._estimate_processing_time(file_size, file_format, config.service_name)
                if request.timeout_seconds < estimated_time:
                    result["warnings"].append(
                        f"Requested timeout ({request.timeout_seconds}s) may be too short. "
                        f"Estimated processing time: {estimated_time}s"
                    )

        except Exception as e:
            logger.warning(f"Service constraint validation error: {e}")

        return result

    def _estimate_processing_time(self, file_size: int, file_format: str, service_name: str) -> int:
        """Estimate processing time for a file."""
        # Base processing time by format (seconds per MB)
        base_times = {
            "pdf": 10,      # 10s per MB for PDFs
            "png": 5,       # 5s per MB for images
            "jpg": 5,
            "jpeg": 5,
            "docx": 8,      # 8s per MB for documents
            "txt": 2,       # 2s per MB for text
            "html": 3       # 3s per MB for HTML
        }

        # Service multipliers
        service_multipliers = {
            "mistral_ocr": 1.0,     # Baseline
            "unstructured": 1.2,    # Slightly slower
            "llamaparse": 1.5       # More complex processing
        }

        size_mb = file_size / (1024 * 1024)
        base_time = base_times.get(file_format, 10) * size_mb
        service_multiplier = service_multipliers.get(service_name, 1.0)

        estimated_time = int(base_time * service_multiplier)

        # Minimum 5 seconds, maximum 600 seconds (10 minutes)
        return max(5, min(estimated_time, 600))

    def get_supported_formats(self) -> dict[str, str]:
        """Get all supported file formats with their MIME types."""
        return self.SUPPORTED_EXTENSIONS.copy()

    def get_format_recommendations(self) -> dict[str, dict[str, Any]]:
        """Get format-specific recommendations and limits."""
        recommendations = {}

        for ext, mime_type in self.SUPPORTED_EXTENSIONS.items():
            max_size = self.DEFAULT_MAX_SIZES.get(ext, 100 * 1024 * 1024)

            recommendations[ext] = {
                "mime_type": mime_type,
                "max_recommended_size": max_size,
                "max_recommended_size_mb": max_size // (1024 * 1024),
                "best_services": self._get_best_services_for_format(ext)
            }

        return recommendations

    def _get_best_services_for_format(self, extension: str) -> list[str]:
        """Get recommended services for a file format."""
        format_service_map = {
            ".pdf": ["mistral_ocr", "unstructured", "llamaparse"],
            ".png": ["mistral_ocr", "unstructured"],
            ".jpg": ["mistral_ocr", "unstructured"],
            ".jpeg": ["mistral_ocr", "unstructured"],
            ".docx": ["unstructured", "llamaparse"],
            ".pptx": ["llamaparse"],
            ".xlsx": ["llamaparse"],
            ".txt": ["unstructured"],
            ".html": ["unstructured"]
        }

        return format_service_map.get(extension, ["unstructured"])
