"""
ParsedDocument model for the root container of parsing results
"""
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from .content_block import ContentBlock

ParsingStatus = Literal["pending", "completed", "failed", "timeout"]
ParsingService = Literal["mistral_ocr", "unstructured", "llamaparse"]


class ParsedDocument(BaseModel):
    """
    Root container for document parsing results with standardized format.

    Represents the complete output of a document parsing operation, including
    metadata about the parsing process, status tracking, and all extracted
    content blocks organized in a consistent structure.
    """

    document_id: str = Field(
        ...,
        min_length=1,
        description="Unique identifier for this parsing operation"
    )

    source_file_path: str = Field(
        ...,
        min_length=1,
        description="Original document URL - either GCS path (gs://bucket/path) or HTTP(S) URL"
    )

    parsing_service: ParsingService = Field(
        ...,
        description="Name of the parsing service used (mistral_ocr|unstructured|llamaparse)"
    )

    status: ParsingStatus = Field(
        ...,
        description="Current processing status (pending|completed|failed|timeout)"
    )

    created_at: datetime = Field(
        ...,
        description="Timestamp when the parsing operation was initiated"
    )

    completed_at: datetime | None = Field(
        None,
        description="Timestamp when the parsing operation finished (success or failure)"
    )

    content_blocks: list[ContentBlock] = Field(
        default_factory=list,
        description="List of parsed content elements extracted from the document"
    )

    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional service-specific metadata and parsing details"
    )

    error_message: str | None = Field(
        None,
        description="Error details if parsing failed, None for successful operations"
    )

    @field_validator('document_id')
    @classmethod
    def validate_document_id(cls, v: str) -> str:
        """Validate that document_id is non-empty and properly formatted"""
        if not v or not v.strip():
            raise ValueError("document_id cannot be empty")
        return v.strip()

    @field_validator('source_file_path')
    @classmethod
    def validate_source_file_path(cls, v: str) -> str:
        """Validate that source_file_path is a valid URL (GCS or HTTP/HTTPS)"""
        if not v or not v.strip():
            raise ValueError("source_file_path cannot be empty")

        v = v.strip()
        # Accept GCS paths or HTTP(S) URLs
        if not (v.startswith('gs://') or v.startswith('http://') or v.startswith('https://')):
            raise ValueError("source_file_path must be a valid URL (gs://, http://, or https://)")

        return v

    @model_validator(mode='after')
    def validate_error_message_for_failed_status(self) -> 'ParsedDocument':
        """
        Validate that error_message is provided when status is 'failed'.

        Failed parsing operations must include an error message explaining
        what went wrong during the parsing process.
        """
        if self.status == 'failed' and not self.error_message:
            raise ValueError("error_message is required when status is 'failed'")

        return self

    @model_validator(mode='after')
    def validate_completed_at_for_finished_status(self) -> 'ParsedDocument':
        """
        Validate that completed_at is set for non-pending operations.

        Operations with status 'completed', 'failed', or 'timeout' should
        have a completion timestamp set.
        """
        if self.status != 'pending' and not self.completed_at:
            raise ValueError(f"completed_at is required when status is '{self.status}'")

        if self.status == 'pending' and self.completed_at:
            raise ValueError("completed_at should not be set when status is 'pending'")

        return self

    @model_validator(mode='after')
    def validate_completion_time_order(self) -> 'ParsedDocument':
        """
        Validate that completed_at is after created_at when both are present.
        """
        if self.completed_at and self.completed_at < self.created_at:
            raise ValueError("completed_at cannot be earlier than created_at")

        return self

    class Config:
        """Pydantic configuration for ParsedDocument model"""
        json_schema_extra = {
            "example": {
                "document_id": "doc_12345",
                "source_file_path": "https://storage.googleapis.com/parsing-bucket/documents/sample.pdf",
                "parsing_service": "mistral_ocr",
                "status": "completed",
                "created_at": "2024-01-15T10:00:00Z",
                "completed_at": "2024-01-15T10:05:30Z",
                "content_blocks": [
                    {
                        "block_id": "block_001",
                        "block_type": "heading",
                        "content": "Document Title",
                        "page_number": 1,
                        "confidence_score": 0.98
                    }
                ],
                "metadata": {
                    "total_pages": 5,
                    "processing_time_seconds": 330,
                    "service_version": "v2.1"
                },
                "error_message": None
            }
        }
