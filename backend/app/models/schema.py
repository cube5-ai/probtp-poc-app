"""
Schema model for database
Represents user-defined data extraction schemas
"""
from datetime import datetime
from sqlalchemy import Column, String, Text, Boolean, Integer, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
import uuid

from app.utils import Base


class Schema(Base):
    """Schema model for storing user-defined data extraction schemas"""
    
    __tablename__ = "schemas"
    
    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    
    # User association
    user_id = Column(String(255), nullable=False, index=True)
    
    # Schema metadata
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    
    # Schema definition as JSON
    schema_definition = Column(JSONB, nullable=False)
    
    # Template and versioning
    base_schema_id = Column(UUID(as_uuid=True), ForeignKey("schemas.id", ondelete="SET NULL"), nullable=True)
    is_template = Column(Boolean, default=False, index=True)
    version = Column(Integer, default=1)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    base_schema = relationship("Schema", remote_side=[id], backref="derived_schemas")
    
    def __repr__(self):
        return f"<Schema(id={self.id}, name={self.name}, user_id={self.user_id})>"
    
    def to_dict(self):
        """Convert schema to dictionary"""
        return {
            "id": str(self.id),
            "user_id": self.user_id,
            "name": self.name,
            "description": self.description,
            "schema_definition": self.schema_definition,
            "base_schema_id": str(self.base_schema_id) if self.base_schema_id else None,
            "is_template": self.is_template,
            "version": self.version,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
