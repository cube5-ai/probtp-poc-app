"""
Pydantic ContentBlock model for API serialization and parsing operations

This model is used for:
- API responses and requests
- Data validation during parsing
- Temporary data structures before database persistence

For database persistence, see ContentBlockDB in content_block_db.py
"""
import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from .bounding_box import BoundingBox

ContentBlockType = Literal["text", "table", "image", "heading", "list"]


class ContentBlock(BaseModel):
    """
    Pydantic model for content blocks during parsing and API operations.

    This model is used for validation and serialization during document parsing
    and API operations. It represents a single piece of content extracted from
    a document, such as text, images, tables, etc.

    For database storage, this model can be converted to ContentBlockDB.
    """

    block_id: str = Field(
        ...,
        min_length=1,
        description="Unique identifier for this content block within the document"
    )

    block_type: ContentBlockType = Field(
        ...,
        description="Type of content in this block (text|table|image|heading|list)"
    )

    content: str = Field(
        ...,
        description="Textual content of the block or reference to binary data for images"
    )

    page_number: int | None = Field(
        None,
        ge=1,
        description="Page number where this block appears (1-indexed), if available"
    )

    position: int | None = Field(
        None,
        ge=0,
        description="Position/rank of this block within the page (0-indexed) to preserve reading order"
    )

    bounding_box: BoundingBox | None = Field(
        None,
        description="Spatial coordinates of the content block on the page, if available"
    )

    confidence_score: float | None = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Parsing confidence score (0.0-1.0) indicating extraction quality"
    )

    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional block-specific attributes and parsing metadata"
    )

    @field_validator('content')
    @classmethod
    def validate_content_required(cls, v: str, info) -> str:
        """
        Validate that content is provided for text-based blocks.

        Text-based blocks (text, heading, list) require non-empty content.
        Image and table blocks may have minimal content (like references).
        """
        if not v or not v.strip():
            # Get block_type from validation context
            block_type = info.data.get('block_type') if info.data else None
            if block_type in ['text', 'heading', 'list']:
                raise ValueError(f"Content is required for {block_type} blocks")

        return v

    @field_validator('block_id')
    @classmethod
    def validate_block_id(cls, v: str) -> str:
        """Validate that block_id is non-empty and properly formatted"""
        if not v or not v.strip():
            raise ValueError("block_id cannot be empty")
        return v.strip()

    class Config:
        """Pydantic configuration for ContentBlock model"""
        json_schema_extra = {
            "example": {
                "block_id": "doc123_p1_b0",
                "block_type": "text",
                "content": "This is a sample paragraph extracted from the document.",
                "page_number": 1,
                "position": 0,
                "bounding_box": {
                    "x": 0.1,
                    "y": 0.2,
                    "width": 0.8,
                    "height": 0.1
                },
                "confidence_score": 0.95,
                "metadata": {
                    "font_size": 12,
                    "font_family": "Arial"
                }
            }
        }

    def to_db_model(self, file_id: uuid.UUID, parsing_service: str, document_id: str) -> 'ContentBlockDB':
        """
        Convert this Pydantic model to a SQLAlchemy database model.

        Args:
            file_id: UUID of the file this block belongs to
            parsing_service: Name of the parsing service used
            document_id: ID of the parsing document

        Returns:
            ContentBlockDB instance ready for database insertion
        """
        from .content_block_db import ContentBlockDB

        # Convert bounding box to JSON-serializable format
        bounding_box_data = None
        if self.bounding_box:
            bounding_box_data = {
                "x": self.bounding_box.x,
                "y": self.bounding_box.y,
                "width": self.bounding_box.width,
                "height": self.bounding_box.height
            }

        return ContentBlockDB(
            file_id=file_id,
            block_id=self.block_id,
            block_type=self.block_type,
            page_number=self.page_number,
            position=self.position,
            content=self.content,
            confidence_score=self.confidence_score,
            bounding_box=bounding_box_data,
            block_metadata=self.metadata,
            parsing_service=parsing_service,
            document_id=document_id
        )

    @classmethod
    def from_db_model(cls, db_model: 'ContentBlockDB') -> 'ContentBlock':
        """
        Convert a SQLAlchemy database model to this Pydantic model.

        Args:
            db_model: ContentBlockDB instance from database

        Returns:
            ContentBlock instance for API serialization
        """
        # Convert bounding box from JSON back to BoundingBox
        bounding_box = None
        if db_model.bounding_box:
            bounding_box = BoundingBox(**db_model.bounding_box)

        return cls(
            block_id=db_model.block_id,
            block_type=db_model.block_type,
            content=db_model.content,
            page_number=db_model.page_number,
            position=db_model.position,
            bounding_box=bounding_box,
            confidence_score=db_model.confidence_score,
            metadata=db_model.block_metadata or {}
        )
