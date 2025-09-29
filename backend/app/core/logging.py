"""
Structured logging configuration using structlog
"""
from typing import Any

import structlog
from structlog import configure, get_logger
from structlog.processors import JSONRenderer, StackInfoRenderer, TimeStamper
from structlog.stdlib import LoggerFactory

from app.core.config import get_settings

settings = get_settings()

# Configure structlog
configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        TimeStamper(fmt="iso"),
        StackInfoRenderer(),
        structlog.processors.format_exc_info,
        JSONRenderer() if not settings.debug else structlog.dev.ConsoleRenderer()
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    logger_factory=LoggerFactory(),
    cache_logger_on_first_use=True,
)

# Get configured logger
logger = get_logger()


class FileUploadLogger:
    """Specialized logger for file upload operations"""

    @staticmethod
    def log_upload_initiated(
        user_id: str,
        project_id: str,
        file_name: str,
        file_size: int,
        file_id: str = None,
        **kwargs
    ) -> None:
        """
        Log when a file upload is initiated
        
        Args:
            user_id: Firebase user ID
            project_id: Project UUID
            file_name: Original filename
            file_size: File size in bytes
            file_id: Generated file UUID (optional)
            **kwargs: Additional context
        """
        logger.info(
            "file_upload_initiated",
            user_id=user_id,
            project_id=project_id,
            file_name=file_name,
            file_size=file_size,
            file_id=file_id,
            **kwargs
        )

    @staticmethod
    def log_upload_completed(
        user_id: str,
        file_id: str,
        project_id: str,
        duration_seconds: float,
        file_size: int = None,
        storage_path: str = None,
        **kwargs
    ) -> None:
        """
        Log when a file upload is completed successfully
        
        Args:
            user_id: Firebase user ID
            file_id: File UUID
            project_id: Project UUID
            duration_seconds: Time taken for upload
            file_size: File size in bytes (optional)
            storage_path: Cloud storage path (optional)
            **kwargs: Additional context
        """
        logger.info(
            "file_upload_completed",
            user_id=user_id,
            file_id=file_id,
            project_id=project_id,
            duration_seconds=round(duration_seconds, 2),
            file_size=file_size,
            storage_path=storage_path,
            **kwargs
        )

    @staticmethod
    def log_upload_failed(
        user_id: str,
        file_id: str,
        project_id: str,
        error: str,
        error_type: str = None,
        duration_seconds: float = None,
        **kwargs
    ) -> None:
        """
        Log when a file upload fails
        
        Args:
            user_id: Firebase user ID
            file_id: File UUID
            project_id: Project UUID
            error: Error message
            error_type: Type of error (optional)
            duration_seconds: Time before failure (optional)
            **kwargs: Additional context
        """
        logger.error(
            "file_upload_failed",
            user_id=user_id,
            file_id=file_id,
            project_id=project_id,
            error=error,
            error_type=error_type,
            duration_seconds=round(duration_seconds, 2) if duration_seconds else None,
            **kwargs
        )

    @staticmethod
    def log_file_deleted(
        user_id: str,
        file_id: str,
        project_id: str,
        file_name: str = None,
        storage_path: str = None,
        **kwargs
    ) -> None:
        """
        Log when a file is deleted
        
        Args:
            user_id: Firebase user ID who deleted the file
            file_id: File UUID
            project_id: Project UUID
            file_name: Original filename (optional)
            storage_path: Cloud storage path (optional)
            **kwargs: Additional context
        """
        logger.info(
            "file_deleted",
            user_id=user_id,
            file_id=file_id,
            project_id=project_id,
            file_name=file_name,
            storage_path=storage_path,
            **kwargs
        )

    @staticmethod
    def log_download_requested(
        user_id: str,
        file_id: str,
        project_id: str,
        file_name: str = None,
        **kwargs
    ) -> None:
        """
        Log when a file download is requested
        
        Args:
            user_id: Firebase user ID
            file_id: File UUID
            project_id: Project UUID
            file_name: Original filename (optional)
            **kwargs: Additional context
        """
        logger.info(
            "file_download_requested",
            user_id=user_id,
            file_id=file_id,
            project_id=project_id,
            file_name=file_name,
            **kwargs
        )


class RequestLogger:
    """Logger for API requests and responses"""

    @staticmethod
    def log_request(
        method: str,
        path: str,
        user_id: str = None,
        request_id: str = None,
        ip_address: str = None,
        **kwargs
    ) -> None:
        """
        Log API request
        
        Args:
            method: HTTP method
            path: Request path
            user_id: Firebase user ID (optional)
            request_id: Request ID for tracing (optional)
            ip_address: Client IP address (optional)
            **kwargs: Additional context
        """
        logger.info(
            "api_request",
            method=method,
            path=path,
            user_id=user_id,
            request_id=request_id,
            ip_address=ip_address,
            **kwargs
        )

    @staticmethod
    def log_response(
        method: str,
        path: str,
        status_code: int,
        duration_ms: float,
        user_id: str = None,
        request_id: str = None,
        **kwargs
    ) -> None:
        """
        Log API response
        
        Args:
            method: HTTP method
            path: Request path
            status_code: HTTP status code
            duration_ms: Request duration in milliseconds
            user_id: Firebase user ID (optional)
            request_id: Request ID for tracing (optional)
            **kwargs: Additional context
        """
        logger.info(
            "api_response",
            method=method,
            path=path,
            status_code=status_code,
            duration_ms=round(duration_ms, 2),
            user_id=user_id,
            request_id=request_id,
            **kwargs
        )


def get_request_logger() -> structlog.stdlib.BoundLogger:
    """Get logger instance for request logging"""
    return logger


def log_exception(
    error: Exception,
    context: dict[str, Any] = None,
    user_id: str = None,
    **kwargs
) -> None:
    """
    Log exception with context

    Args:
        error: Exception instance
        context: Additional context dictionary
        user_id: Firebase user ID (optional)
        **kwargs: Additional context
    """
    error_context = {
        "error_type": type(error).__name__,
        "error_message": str(error),
        "user_id": user_id,
        **(context or {}),
        **kwargs
    }

    logger.error(
        "exception_occurred",
        **error_context,
        exc_info=True
    )


class ParsingLogger:
    """Specialized logger for document parsing operations"""

    @staticmethod
    def log_parsing_initiated(
        file_path: str,
        service_name: str,
        correlation_id: str,
        file_size: int = None,
        timeout_seconds: int = None,
        **kwargs
    ) -> None:
        """
        Log when document parsing is initiated

        Args:
            file_path: GCS path to the document
            service_name: Parsing service being used
            correlation_id: Unique ID for tracing this operation
            file_size: File size in bytes (optional)
            timeout_seconds: Parsing timeout (optional)
            **kwargs: Additional context
        """
        logger.info(
            "parsing_initiated",
            file_path=file_path,
            service_name=service_name,
            correlation_id=correlation_id,
            file_size=file_size,
            timeout_seconds=timeout_seconds,
            **kwargs
        )

    @staticmethod
    def log_parsing_completed(
        file_path: str,
        service_name: str,
        correlation_id: str,
        duration_seconds: float,
        status: str,
        blocks_count: int = None,
        pages_count: int = None,
        **kwargs
    ) -> None:
        """
        Log when document parsing is completed

        Args:
            file_path: GCS path to the document
            service_name: Parsing service used
            correlation_id: Unique ID for tracing this operation
            duration_seconds: Time taken for parsing
            status: Final parsing status (completed, failed, timeout)
            blocks_count: Number of content blocks extracted (optional)
            pages_count: Number of pages processed (optional)
            **kwargs: Additional context
        """
        logger.info(
            "parsing_completed",
            file_path=file_path,
            service_name=service_name,
            correlation_id=correlation_id,
            duration_seconds=round(duration_seconds, 2),
            status=status,
            blocks_count=blocks_count,
            pages_count=pages_count,
            **kwargs
        )

    @staticmethod
    def log_parsing_failed(
        file_path: str,
        service_name: str,
        correlation_id: str,
        error: str,
        error_type: str = None,
        duration_seconds: float = None,
        **kwargs
    ) -> None:
        """
        Log when document parsing fails

        Args:
            file_path: GCS path to the document
            service_name: Parsing service that failed
            correlation_id: Unique ID for tracing this operation
            error: Error message
            error_type: Type of error (optional)
            duration_seconds: Time before failure (optional)
            **kwargs: Additional context
        """
        logger.error(
            "parsing_failed",
            file_path=file_path,
            service_name=service_name,
            correlation_id=correlation_id,
            error=error,
            error_type=error_type,
            duration_seconds=round(duration_seconds, 2) if duration_seconds else None,
            **kwargs
        )

    @staticmethod
    def log_validation_performed(
        file_path: str,
        service_name: str,
        correlation_id: str,
        valid: bool,
        file_size: int = None,
        file_format: str = None,
        errors: list = None,
        **kwargs
    ) -> None:
        """
        Log when file validation is performed

        Args:
            file_path: GCS path to the file
            service_name: Target parsing service
            correlation_id: Unique ID for tracing this operation
            valid: Whether file passed validation
            file_size: File size in bytes (optional)
            file_format: Detected file format (optional)
            errors: List of validation errors (optional)
            **kwargs: Additional context
        """
        logger.info(
            "validation_performed",
            file_path=file_path,
            service_name=service_name,
            correlation_id=correlation_id,
            valid=valid,
            file_size=file_size,
            file_format=file_format,
            error_count=len(errors) if errors else 0,
            **kwargs
        )

    @staticmethod
    def log_service_health_checked(
        service_name: str,
        status: str,
        response_time_ms: float,
        endpoint: str = None,
        **kwargs
    ) -> None:
        """
        Log service health check results

        Args:
            service_name: Name of the parsing service
            status: Health status (available, unavailable, degraded)
            response_time_ms: Response time in milliseconds
            endpoint: Health check endpoint (optional)
            **kwargs: Additional context
        """
        logger.info(
            "service_health_checked",
            service_name=service_name,
            health_status=status,
            response_time_ms=round(response_time_ms, 2),
            endpoint=endpoint,
            **kwargs
        )

    @staticmethod
    def log_performance_metrics(
        service_name: str,
        file_size: int,
        page_count: int,
        duration_seconds: float,
        status: str,
        correlation_id: str,
        **kwargs
    ) -> None:
        """
        Log parsing performance metrics

        Args:
            service_name: Name of parsing service used
            file_size: Size of processed file in bytes
            page_count: Number of pages processed
            duration_seconds: Processing duration in seconds
            status: Final processing status
            correlation_id: Request correlation ID
            **kwargs: Additional context
        """
        throughput_pages = page_count / max(duration_seconds, 0.001)
        throughput_bytes = file_size / max(duration_seconds, 0.001)

        logger.info(
            "parsing_performance_metrics",
            service_name=service_name,
            file_size_bytes=file_size,
            page_count=page_count,
            duration_seconds=round(duration_seconds, 2),
            status=status,
            correlation_id=correlation_id,
            throughput_pages_per_second=round(throughput_pages, 2),
            throughput_bytes_per_second=round(throughput_bytes, 2),
            **kwargs
        )
