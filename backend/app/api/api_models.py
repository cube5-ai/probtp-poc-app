"""
Pydantic schemas for API request/response models
"""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, validator


class ProjectCreateRequest(BaseModel):
    """Request schema for creating a project"""

    name: str = Field(..., min_length=1, max_length=255, description="Project name")
    description: str | None = Field(None, description="Project description")


class ProjectResponse(BaseModel):
    """Response schema for project data"""

    id: UUID = Field(..., description="Project identifier")
    name: str = Field(..., description="Project name")
    description: str | None = Field(None, description="Project description")
    created_by: str = Field(..., description="User who created the project (Firebase UID)")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


class FileUploadRequest(BaseModel):
    """Request schema for initiating file upload"""

    filename: str = Field(..., min_length=1, max_length=500, description="Original filename")
    file_size: int = Field(..., gt=0, description="File size in bytes")

    @validator('filename')
    def validate_filename(cls, v):
        """Validate filename has PDF extension"""
        if not v.lower().endswith('.pdf'):
            raise ValueError('Only PDF files are allowed')
        return v

    @validator('file_size')
    def validate_file_size(cls, v):
        """Validate file size is within limits"""
        max_size = 100 * 1024 * 1024  # 100MB in bytes
        if v > max_size:
            raise ValueError(f'File size must not exceed {max_size} bytes (100MB)')
        return v


class FileUploadResponse(BaseModel):
    """Response schema for file upload initiation"""

    upload_id: UUID = Field(..., description="Unique identifier for this upload")
    upload_url: str = Field(..., description="Signed URL for direct upload to cloud storage")
    upload_method: str = Field(default="PUT", description="HTTP method to use for upload")
    expires_at: datetime = Field(..., description="When the upload URL expires")
    max_file_size: int = Field(..., description="Maximum allowed file size in bytes")


class FileConfirmRequest(BaseModel):
    """Request schema for confirming file upload completion"""

    md5_hash: str | None = Field(None, min_length=32, max_length=32, description="MD5 hash for integrity check")


class FileConfirmResponse(BaseModel):
    """Response schema for file upload confirmation"""

    file_id: UUID = Field(..., description="File identifier")
    status: str = Field(..., description="File status after confirmation")
    message: str = Field(..., description="Confirmation message")


class FileUpdateRequest(BaseModel):
    """Request schema for updating file metadata"""

    original_name: str | None = Field(None, min_length=1, max_length=500, description="New filename")

    @validator('original_name')
    def validate_filename(cls, v):
        """Validate filename if provided"""
        if v:
            # Ensure no path traversal attempts
            if '/' in v or '\\' in v:
                raise ValueError('Filename cannot contain path separators')
        return v


class FileUpdateResponse(BaseModel):
    """Response schema for file update"""

    file_id: UUID = Field(..., description="File identifier")
    original_name: str = Field(..., description="Updated filename")
    message: str = Field(..., description="Update confirmation message")


class FileStatusResponse(BaseModel):
    """Response schema for file status check"""

    file_id: UUID = Field(..., description="File identifier")
    status: str = Field(..., description="Current file status")
    progress: int | None = Field(None, ge=0, le=100, description="Upload progress percentage")
    updated_at: datetime = Field(..., description="Last status update time")
    error_message: str | None = Field(None, description="Error message if status is failed")


class UserInfo(BaseModel):
    """User information schema"""

    id: str = Field(..., description="User identifier")
    email: str = Field(..., description="User email address")
    name: str | None = Field(None, description="User display name")


class FileListItem(BaseModel):
    """Schema for file item in list response"""

    id: UUID = Field(..., description="File identifier")
    original_name: str = Field(..., description="Original filename")
    file_size: int = Field(..., description="File size in bytes")
    status: str = Field(..., description="File status")
    uploaded_by: UserInfo = Field(..., description="User who uploaded the file")
    created_at: datetime = Field(..., description="Upload timestamp")
    download_url: str | None = Field(None, description="Temporary download URL")
    view_url: str | None = Field(None, description="Temporary view URL for inline display")


class PaginationInfo(BaseModel):
    """Pagination information schema"""

    page: int = Field(..., ge=1, description="Current page number")
    size: int = Field(..., ge=1, description="Items per page")
    total: int = Field(..., ge=0, description="Total number of items")
    pages: int = Field(..., ge=0, description="Total number of pages")


class FileListResponse(BaseModel):
    """Response schema for file list"""

    files: list[FileListItem] = Field(..., description="List of files")
    pagination: PaginationInfo = Field(..., description="Pagination information")


class ErrorResponse(BaseModel):
    """Standard error response schema"""

    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Human-readable error message")
    details: dict | None = Field(None, description="Additional error details")
