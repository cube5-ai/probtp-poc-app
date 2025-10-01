"""
SQLAlchemy ContentBlock model for database storage
"""
from sqlalchemy import JSON, Column, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.models.base import BaseModel


class ContentBlockDB(BaseModel):
    """
    Database model for storing parsed content blocks.

    This model represents content blocks extracted from documents during parsing,
    stored in the database with references to their source files.
    """

    __tablename__ = "content_blocks"

    # Foreign key to files table
    file_id = Column(
        UUID(as_uuid=True),
        ForeignKey("files.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Block identification and ordering
    block_id = Column(String(200), nullable=False, index=True)
    block_type = Column(String(50), nullable=False, index=True)  # text, table, image, heading, list
    page_number = Column(Integer, nullable=True, index=True)
    position = Column(Integer, nullable=True, index=True)  # Position within page for ordering

    # Content
    content = Column(Text, nullable=False)

    # Quality metrics
    confidence_score = Column(Float, nullable=True)

    # Spatial information (stored as JSON for flexibility)
    bounding_box = Column(JSON, nullable=True)  # {x, y, width, height}

    # Additional metadata (stored as JSON for flexibility)
    block_metadata = Column(JSON, nullable=True, default=dict)

    # Parsing information
    parsing_service = Column(String(100), nullable=True)  # mistral_ocr, unstructured, etc.
    document_id = Column(String(200), nullable=True)  # Original parsing document ID

    # Relationships
    file = relationship("File", back_populates="content_blocks")

    def __repr__(self) -> str:
        return f"<ContentBlockDB(id={self.id}, file_id={self.file_id}, type='{self.block_type}', page={self.page_number})>"

    @property
    def is_image(self) -> bool:
        """Check if this block contains an image"""
        return self.block_type == "image"

    @property
    def is_text(self) -> bool:
        """Check if this block contains text content"""
        return self.block_type in ("text", "heading", "list")

    @property
    def is_table(self) -> bool:
        """Check if this block contains a table"""
        return self.block_type == "table"
