"""
File model for uploaded documents
"""
from datetime import datetime

from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.models.base import BaseModel


class File(BaseModel):
    """File model for managing uploaded documents"""

    __tablename__ = "files"

    project_id = Column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False
    )
    original_name = Column(String(500), nullable=False)
    storage_path = Column(String(1000), nullable=False)
    file_size = Column(BigInteger, nullable=False)  # in bytes
    mime_type = Column(String(100), default='application/pdf', nullable=False)
    md5_hash = Column(String(32), nullable=True)  # for deduplication/integrity
    status = Column(
        String(50),
        default='pending',
        nullable=False
        # Status validation: pending, uploading, ready, failed
    )
    upload_url = Column(Text, nullable=True)  # signed URL for upload
    upload_url_expires_at = Column(DateTime(timezone=True), nullable=True)
    uploaded_by = Column(String(128), nullable=False)  # Firebase user ID (string)
    deleted_at = Column(DateTime(timezone=True), nullable=True)  # soft delete
    error_message = Column(Text, nullable=True)  # populated if status = 'failed'

    # Relationships
    project = relationship("Project", back_populates="files")
    content_blocks = relationship("ContentBlockDB", back_populates="file", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<File(id={self.id}, name='{self.original_name}', status='{self.status}')>"

    @property
    def is_deleted(self) -> bool:
        """Check if file is soft deleted"""
        return self.deleted_at is not None

    @property
    def is_ready(self) -> bool:
        """Check if file is ready for download"""
        return self.status == 'ready' and not self.is_deleted

    @property
    def is_pending(self) -> bool:
        """Check if file upload is pending"""
        return self.status == 'pending'

    @property
    def is_uploading(self) -> bool:
        """Check if file is currently uploading"""
        return self.status == 'uploading'

    @property
    def is_failed(self) -> bool:
        """Check if file upload failed"""
        return self.status == 'failed'

    @property
    def upload_expired(self) -> bool:
        """Check if upload URL has expired"""
        if not self.upload_url_expires_at:
            return True
        return datetime.utcnow() > self.upload_url_expires_at.replace(tzinfo=None)

    def soft_delete(self) -> None:
        """Mark file as deleted (soft delete)"""
        self.deleted_at = datetime.utcnow()

    def mark_as_uploading(self) -> None:
        """Mark file status as uploading"""
        self.status = 'uploading'

    def mark_as_ready(self) -> None:
        """Mark file status as ready"""
        self.status = 'ready'

    def mark_as_failed(self, error_message: str = None) -> None:
        """Mark file status as failed with optional error message"""
        self.status = 'failed'
        if error_message:
            self.error_message = error_message
