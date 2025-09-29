"""
Project model for database operations
"""
from sqlalchemy import Column, String, Text
from sqlalchemy.orm import relationship

from app.models.base import BaseModel


class Project(BaseModel):
    """Project model for organizing files and users"""

    __tablename__ = "projects"

    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    created_by = Column(String(128), nullable=False)  # Firebase user ID (string)

    # Relationships
    members = relationship("ProjectMember", back_populates="project", cascade="all, delete-orphan")
    files = relationship("File", back_populates="project", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Project(id={self.id}, name='{self.name}')>"
