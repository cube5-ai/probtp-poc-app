"""
Custom error classes and error handling utilities
"""
from typing import Any

from fastapi import HTTPException
from google.cloud.exceptions import Forbidden, GoogleCloudError, NotFound


class FileUploadError(HTTPException):
    """Custom exception for file upload related errors"""

    def __init__(self, detail: str, status_code: int = 400):
        super().__init__(status_code=status_code, detail=detail)


class UploadErrors:
    """Predefined error responses for file upload operations"""

    # Client errors (4xx)
    FILE_TOO_LARGE = FileUploadError("File size exceeds maximum allowed size of 100MB", 413)
    INVALID_FILE_TYPE = FileUploadError("Only PDF files are allowed", 415)
    INVALID_PROJECT = FileUploadError("Project not found or access denied", 404)
    FILE_NOT_FOUND = FileUploadError("File not found", 404)
    NO_PERMISSION = FileUploadError("Insufficient permissions for this operation", 403)
    UPLOAD_EXPIRED = FileUploadError("Upload URL has expired, please request a new one", 410)
    INVALID_FILE_STATUS = FileUploadError("File is not in the correct status for this operation", 409)
    DUPLICATE_FILENAME = FileUploadError("A file with this name already exists in the project", 409)

    # Server errors (5xx)
    UPLOAD_FAILED = FileUploadError("File upload failed due to server error", 500)
    STORAGE_ERROR = FileUploadError("Cloud storage operation failed", 500)
    DATABASE_ERROR = FileUploadError("Database operation failed", 500)

    @staticmethod
    def handle_storage_error(error: Exception) -> FileUploadError:
        """
        Convert Google Cloud Storage errors to appropriate API errors
        
        Args:
            error: Exception from Google Cloud Storage operation
        
        Returns:
            FileUploadError with appropriate status code and message
        """
        if isinstance(error, NotFound):
            return FileUploadError("Storage location or file not found", 404)
        elif isinstance(error, Forbidden):
            return FileUploadError("Storage permission denied", 403)
        elif isinstance(error, GoogleCloudError):
            return FileUploadError(f"Cloud storage error: {str(error)}", 500)
        else:
            return FileUploadError(f"Unexpected storage error: {str(error)}", 500)

    @staticmethod
    def handle_database_error(error: Exception) -> FileUploadError:
        """
        Convert database errors to appropriate API errors
        
        Args:
            error: Exception from database operation
        
        Returns:
            FileUploadError with appropriate status code and message
        """
        # Log the actual error for debugging while returning generic message to client
        error_msg = str(error)

        if "duplicate key value" in error_msg.lower():
            return FileUploadError("Resource already exists", 409)
        elif "foreign key constraint" in error_msg.lower():
            return FileUploadError("Referenced resource not found", 404)
        elif "not null constraint" in error_msg.lower():
            return FileUploadError("Missing required field", 400)
        else:
            return UploadErrors.DATABASE_ERROR


class AuthenticationError(HTTPException):
    """Custom exception for authentication errors"""

    def __init__(self, detail: str = "Authentication failed"):
        super().__init__(status_code=401, detail=detail)


class AuthorizationError(HTTPException):
    """Custom exception for authorization errors"""

    def __init__(self, detail: str = "Access denied"):
        super().__init__(status_code=403, detail=detail)


class ValidationError(HTTPException):
    """Custom exception for validation errors"""

    def __init__(self, detail: str, field: str = None):
        if field:
            detail = f"{field}: {detail}"
        super().__init__(status_code=422, detail=detail)


def create_error_response(
    status_code: int,
    message: str,
    error_code: str = None,
    details: dict[str, Any] = None
) -> dict[str, Any]:
    """
    Create standardized error response format
    
    Args:
        status_code: HTTP status code
        message: Error message
        error_code: Optional error code for client handling
        details: Optional additional error details
    
    Returns:
        Standardized error response dictionary
    """
    response = {
        "error": {
            "status_code": status_code,
            "message": message,
            "timestamp": "2024-01-01T00:00:00Z"  # Will be replaced with actual timestamp
        }
    }

    if error_code:
        response["error"]["error_code"] = error_code

    if details:
        response["error"]["details"] = details

    return response
