"""
Project member model for user-project relationships
"""
from sqlalchemy import Column, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.models.base import BaseModel


class ProjectMember(BaseModel):
    """Project member model for managing user access to projects"""

    __tablename__ = "project_members"

    project_id = Column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False
    )
    user_id = Column(String(128), nullable=False)  # Firebase user ID (string)
    role = Column(
        String(50),
        nullable=False,
        # Role validation handled at application level for flexibility
    )
    added_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    added_by = Column(String(128), nullable=True)  # Firebase user ID of who added this member (string)

    # Relationships
    project = relationship("Project", back_populates="members")

    # Constraints
    __table_args__ = (
        UniqueConstraint('project_id', 'user_id', name='uq_project_user'),
    )

    def __repr__(self) -> str:
        return f"<ProjectMember(project_id={self.project_id}, user_id={self.user_id}, role='{self.role}')>"

    @property
    def is_owner(self) -> bool:
        """Check if member has owner role"""
        return self.role == 'owner'

    @property
    def is_editor(self) -> bool:
        """Check if member has editor role"""
        return self.role == 'editor'

    @property
    def is_viewer(self) -> bool:
        """Check if member has viewer role"""
        return self.role == 'viewer'

    @property
    def can_upload(self) -> bool:
        """Check if member can upload files"""
        return self.role in ['owner', 'editor']

    @property
    def can_delete_any_file(self) -> bool:
        """Check if member can delete any file in project"""
        return self.role == 'owner'
