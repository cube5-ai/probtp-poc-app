"""
Base database model classes
"""
import uuid
from typing import Any

from sqlalchemy import Column, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()


class TimestampMixin:
    """Mixin for adding timestamp fields to models"""

    created_at = Column(
        DateTime(timezone=True),
        default=func.now(),
        nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=func.now(),
        onupdate=func.now(),
        nullable=False
    )


class BaseModel(Base, TimestampMixin):
    """Base model class with common fields"""

    __abstract__ = True

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False
    )

    def to_dict(self) -> dict[str, Any]:
        """Convert model instance to dictionary"""
        return {
            column.name: getattr(self, column.name)
            for column in self.__table__.columns
        }
